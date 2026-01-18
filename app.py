"""
GraphRAG V4 Streamlit Frontend
Basic querying interface for the graph-only pipeline
"""
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from database.neo4j_client import Neo4jClient
from query.global_query_v4 import global_query, format_global_results

# Page configuration
st.set_page_config(
    page_title="GraphRAG V4 - Graph Query Interface",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .query-result {
        background: #ffffff;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e1e5e9;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'query_history' not in st.session_state:
    st.session_state.query_history = []

def connect_to_neo4j():
    """Connect to Neo4j database"""
    try:
        client = Neo4jClient()
        if client.verify_connection():
            st.session_state.connected = True
            st.session_state.client = client
            return True, "✅ Connected to Neo4j successfully!"
        else:
            return False, "❌ Failed to connect to Neo4j"
    except Exception as e:
        return False, f"❌ Connection error: {str(e)}"

def get_graph_statistics():
    """Get basic graph statistics"""
    try:
        with st.session_state.client.driver.session() as session:
            # Entity statistics
            entities = session.run("MATCH (e:Entity) RETURN count(e) as count").single()["count"]
            
            # Relationship statistics
            relationships = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            
            # Section statistics
            sections = session.run("MATCH (s:Section) RETURN count(s) as count").single()["count"]
            
            # Community statistics
            communities = session.run("MATCH (c:Community) RETURN count(c) as count").single()["count"]
            
            # Salience distribution
            salience_query = """
            MATCH (e:Entity) 
            WHERE e.salience IS NOT NULL
            RETURN e.salience as salience, count(e) as count
            ORDER BY count DESC
            """
            salience_data = list(session.run(salience_query))
            
            return {
                'entities': entities,
                'relationships': relationships,
                'sections': sections,
                'communities': communities,
                'salience_distribution': salience_data
            }
    except Exception as e:
        st.error(f"Error getting statistics: {str(e)}")
        return None

def execute_query(query_text, query_type="custom"):
    """Execute a query against the graph"""
    try:
        with st.session_state.client.driver.session() as session:
            if query_type == "custom":
                result = session.run(query_text)
                records = [dict(record) for record in result]
                return records, None
            else:
                # Use predefined query types
                results, context = global_query(query_text, st.session_state.client)
                return results, context
    except Exception as e:
        return None, f"Query error: {str(e)}"

# Main UI
def main():
    # Header
    st.markdown('<h1 class="main-header">🔍 GraphRAG V4 Query Interface</h1>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📊 Graph Statistics")
        
        if not st.session_state.connected:
            if st.button("🔌 Connect to Neo4j", type="primary"):
                success, message = connect_to_neo4j()
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        else:
            st.success("✅ Connected to Neo4j")
            
            # Get and display statistics
            stats = get_graph_statistics()
            if stats:
                st.metric("📝 Entities", stats['entities'])
                st.metric("🔗 Relationships", stats['relationships'])
                st.metric("📄 Sections", stats['sections'])
                st.metric("🏘️ Communities", stats['communities'])
                
                # Salience distribution chart
                if stats['salience_distribution']:
                    salience_df = pd.DataFrame(stats['salience_distribution'])
                    fig = px.pie(salience_df, values='count', names='salience', title="Entity Salience")
                    st.plotly_chart(fig, use_container_width=True)
            
            if st.button("🔄 Refresh Statistics"):
                st.rerun()
            
            if st.button("🔌 Disconnect"):
                st.session_state.connected = False
                if 'client' in st.session_state:
                    st.session_state.client.close()
                st.rerun()
    
    # Main content area
    if not st.session_state.connected:
        st.warning("⚠️ Please connect to Neo4j to start querying")
        st.info("📋 Make sure Neo4j is running and check your connection settings in `config/settings.py`")
        return
    
    # Query interface
    st.header("💬 Query Your Graph")
    
    # Query tabs
    tab1, tab2, tab3 = st.tabs(["🔍 Quick Queries", "📝 Custom Query", "📊 Query History"])
    
    with tab1:
        st.subheader("Pre-defined Graph Queries")
        
        # Predefined queries
        predefined_queries = {
            "Show all CORE entities": """
                MATCH (e:Entity) 
                WHERE e.salience = 'CORE'
                RETURN e.name as entity, e.type as type, e.description as description
                LIMIT 20
            """,
            "Show relationships between important entities": """
                MATCH (e1:Entity)-[r]->(e2:Entity)
                WHERE e1.salience IN ['CORE', 'IMPORTANT'] AND e2.salience IN ['CORE', 'IMPORTANT']
                RETURN e1.name as source, type(r) as relationship, e2.name as target
                LIMIT 15
            """,
            "Show community structure": """
                MATCH (e:Entity)
                WHERE e.community_id IS NOT NULL
                RETURN e.community_id as community, collect(e.name) as members
                ORDER BY community
            """,
            "Show sections and their entities": """
                MATCH (s:Section)-[:MENTIONS]->(e:Entity)
                RETURN s.title as section, collect(e.name) as entities
                ORDER BY s.section_id
            """,
            "Most connected entities": """
                MATCH (e:Entity)-[r]-()
                RETURN e.name as entity, count(r) as connections
                ORDER BY connections DESC
                LIMIT 10
            """
        }
        
        selected_query = st.selectbox("Select a predefined query:", list(predefined_queries.keys()))
        
        if st.button("🚀 Execute Query", type="primary"):
            query_text = predefined_queries[selected_query]
            with st.spinner("Executing query..."):
                results, error = execute_query(query_text, "custom")
                
                if error:
                    st.error(error)
                elif results:
                    st.success(f"✅ Found {len(results)} results")
                    
                    # Display results in a table
                    df = pd.DataFrame(results)
                    st.dataframe(df, use_container_width=True)
                    
                    # Add to query history
                    st.session_state.query_history.append({
                        'timestamp': datetime.now(),
                        'query': selected_query,
                        'cypher': query_text,
                        'results_count': len(results)
                    })
                else:
                    st.info("No results found")
    
    with tab2:
        st.subheader("Custom Cypher Query")
        
        # Custom query editor
        query_text = st.text_area(
            "Enter your Cypher query:",
            placeholder="MATCH (e:Entity) RETURN e.name LIMIT 10",
            height=150
        )
        
        if st.button("🔍 Execute Custom Query", type="primary"):
            if query_text.strip():
                with st.spinner("Executing custom query..."):
                    results, error = execute_query(query_text, "custom")
                    
                    if error:
                        st.error(error)
                    elif results:
                        st.success(f"✅ Found {len(results)} results")
                        
                        # Display results
                        df = pd.DataFrame(results)
                        st.dataframe(df, use_container_width=True)
                        
                        # Add to query history
                        st.session_state.query_history.append({
                            'timestamp': datetime.now(),
                            'query': 'Custom Query',
                            'cypher': query_text,
                            'results_count': len(results)
                        })
                    else:
                        st.info("No results found")
            else:
                st.warning("⚠️ Please enter a query")
    
    with tab3:
        st.subheader("Query History")
        
        if st.session_state.query_history:
            history_df = pd.DataFrame(st.session_state.query_history)
            history_df['timestamp'] = history_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            st.dataframe(history_df, use_container_width=True)
            
            # Clear history button
            if st.button("🗑️ Clear History"):
                st.session_state.query_history = []
                st.rerun()
        else:
            st.info("No query history yet. Run some queries to see them here!")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🚀 GraphRAG V4 - Graph-Only Query Interface</p>
        <p>Query your knowledge graph without embeddings</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
