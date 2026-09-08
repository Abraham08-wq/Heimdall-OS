from typing import Dict, Any, List
from app.infrastructure.graph import graph_db
# In prod, import LLM service here

class NLQueryEngine:
    """
    Translates Natural Language to Database Queries (Text-to-SQL/Cypher).
    """
    
    def __init__(self):
        # Maps intent keys to query templates
        self.query_templates = {
            "why_high_risk": {
                "type": "explanation",
                "logic": "Retrieve risk factors from RiskEngine" 
            },
            "recent_relationships": {
                "type": "cypher",
                "template": "MATCH (n)-[r]-(m) WHERE r.created_at > datetime() - duration('P30D') RETURN n, r, m LIMIT 20"
            },
            "show_email_link": {
                "type": "cypher",
                "template": "MATCH (p:Person)-[:OWNS]->(e:Email {address: $email}) RETURN p"
            }
        }

    async def parse_intent(self, user_query: str) -> Dict[str, Any]:
        """
        Simulates LLM Intent Classification.
        """
        user_query = user_query.lower()
        
        if "risk" in user_query:
            return {"intent": "why_high_risk", "params": {}}
            
        if "relationship" in user_query and "30 days" in user_query:
            return {"intent": "recent_relationships", "params": {}}
            
        if "linked to email" in user_query:
            email = user_query.split("email ")[-1].strip()
            return {"intent": "show_email_link", "params": {"email": email}}
            
        return {"intent": "search_entity", "params": {"query": user_query}}

    async def execute(self, user_query: str) -> Any:
        # 1. Parse
        parsed = await self.parse_intent(user_query)
        intent = parsed["intent"]
        params = parsed["params"]
        
        # 2. Route & Execute
        if intent == "search_entity":
            # Fallback to simple name search
            # In a real app this would query the DB
            return {
                "type": "search_results",
                "data": [
                    {"id": "e1", "name": f"Entity matching '{params['query']}'", "type": "Person", "risk": 45},
                    {"id": "e2", "name": "Related Device", "type": "Device", "risk": 12}
                ]
            }
            
        template = self.query_templates.get(intent)
        
        if template and template["type"] == "cypher":
            # return await graph_db.execute_query(template['template'], params)
            return {"type": "graph_result", "data": "Simulated Graph Data"}
            
        elif template and template["type"] == "explanation":
            return {"type": "text", "message": "Analysis: The high risk is driven by 3 factors: Breach Exposure, Connection to Malicious Domain X, and Flight Risk."}
            
        return {"type": "text", "message": "I'm not sure how to answer that yet."}

nl_engine = NLQueryEngine()
