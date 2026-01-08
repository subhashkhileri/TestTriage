"""
Script to sync Jira issues from RHDHBUGS project to ChromaDB for semantic similarity search.
Run this script periodically (e.g., via cron job every 6 hours) to keep the vector DB updated.

Environment Variables:
    JIRA_PAT: Jira Personal Access Token (required)
    GOOGLE_API_KEY: Google API key for embedding model (required)
    CHROMA_DB_DIR: ChromaDB persistence directory (optional, defaults to ./chroma_db)
"""

import os
from datetime import datetime
from typing import List, Dict
from jira import JIRA
import chromadb
from chromadb.config import Settings
import google.generativeai as genai
import argparse
import json
import re
from config.settings import settings


class JiraChromaSync:
    def __init__(self,
                 jira_server: str = "https://issues.redhat.com/",
                 jira_token: str = None,
                 chroma_persist_directory: str = settings.chroma_db_dir,
                 embedding_model: str = "models/text-embedding-004"):
        """
        Initialize Jira to ChromaDB sync.

        Args:
            jira_server: Jira server URL
            jira_token: Jira PAT token
            chroma_persist_directory: Directory to persist ChromaDB
            embedding_model: Google embedding model name
        """
        self.jira_token = jira_token or os.getenv("JIRA_PAT")
        if not self.jira_token:
            raise ValueError("JIRA_PAT environment variable not set")

        # Initialize Google API
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        genai.configure(api_key=google_api_key)

        # Initialize Jira client
        self.jira_client = JIRA(
            server=jira_server,
            token_auth=self.jira_token
        )

        # Initialize ChromaDB client with persistence
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )

        # Store embedding model name
        print(f"Using Google embedding model: {embedding_model}")
        self.embedding_model_name = embedding_model

        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="jira_issues",
            metadata={"description": "RHDHBUGS Jira issues for semantic similarity search"}
        )
        
    def fetch_jira_issues(self, 
                         project_key: str = "RHDHBUGS",
                         max_results: int = 1000,
                         start_at: int = 0) -> List[Dict]:
        """
        Fetch issues from Jira project.
        
        Args:
            project_key: Jira project key
            max_results: Maximum number of results per query
            start_at: Start index for pagination
            
        Returns:
            List of issue dictionaries
        """
        print(f"Fetching issues from project: {project_key}")
        
        # JQL query to fetch all issues from the project
        # Ordering by updated date to get most recent first
        jql_query = f"project = {project_key} ORDER BY updated DESC"
        
        all_issues = []
        
        try:
            # Paginate through all results
            while True:
                issues = self.jira_client.search_issues(
                    jql_query,
                    startAt=start_at,
                    maxResults=max_results,
                    fields='key,summary,description,status,issuetype,created,updated,labels,components,resolution,priority'
                )
                
                if not issues:
                    break
                
                print(f"Fetched {len(issues)} issues (offset: {start_at})")
                
                for issue in issues:
                    issue_data = self._extract_issue_data(issue)
                    all_issues.append(issue_data)
                
                # Check if we've fetched all issues
                if len(issues) < max_results:
                    break
                    
                start_at += max_results
            
            print(f"Total issues fetched: {len(all_issues)}")
            return all_issues
            
        except Exception as e:
            print(f"Error fetching Jira issues: {e}")
            raise
    
    def _normalize_description(self, description: str) -> str:
        """
        Normalize Jira description by cleaning up escape sequences,
        special characters, and formatting artifacts.
        
        Args:
            description: Raw description text from Jira
            
        Returns:
            Cleaned and normalized description text
        """
        if not description:
            return ""
        
        # Replace \r\n with \n
        text = description.replace('\r\n', '\n')
        
        # Replace non-breaking spaces (\xa0) with regular spaces
        text = text.replace('\xa0', ' ')
        
        # Remove or simplify Jira-specific markup
        # Remove h1., h2., h3., etc. headers (keep the text, remove markup)
        text = re.sub(r'h[1-6]\.\s*', '', text)
        
        # Convert {code:language} blocks to plain text or markdown
        # Remove opening {code:language} or {code}
        text = re.sub(r'\{code:[^}]+\}', '\n```\n', text)
        text = re.sub(r'\{code\}', '\n```\n', text)
        
        # Remove other Jira markup
        text = re.sub(r'\{quote\}', '\n> ', text)
        text = re.sub(r'\{noformat\}', '\n', text)
        
        # Clean up excessive whitespace
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Replace multiple newlines with maximum of 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _extract_issue_data(self, issue) -> Dict:
        """
        Extract relevant data from Jira issue.
        
        Args:
            issue: Jira issue object
            
        Returns:
            Dictionary with issue data
        """
        fields = issue.fields
        
        # Extract and normalize description
        raw_description = fields.description if fields.description else ""
        description = self._normalize_description(raw_description)
        
        # Extract labels
        labels = fields.labels if fields.labels else []
        
        # Extract components
        components = [comp.name for comp in fields.components] if fields.components else []
        
        # Extract resolution
        resolution = fields.resolution.name if fields.resolution else "Unresolved"
        
        # Extract priority
        priority = fields.priority.name if fields.priority else "Unknown"

        data = {
            "key": issue.key,
            "summary": fields.summary,
            "description": description,
            "status": fields.status.name,
            "issuetype": fields.issuetype.name,
            "created": str(fields.created),
            "updated": str(fields.updated),
            "labels": labels,
            "components": components,
            "resolution": resolution,
            "priority": priority,
            "url": f"https://issues.redhat.com/browse/{issue.key}"
        }
        
        return data
    
    def _create_searchable_text(self, issue_data: Dict) -> str:
        """
        Create a comprehensive searchable text from issue data.
        This text will be embedded for similarity search.
        
        Args:
            issue_data: Dictionary with issue data
            
        Returns:
            Combined text for embedding
        """
        components = [
            f"Summary: {issue_data['summary']}",
            # f"Description: {issue_data['description'][:500]}",  # Limit description length
            f"Description: {issue_data['description']}",  # Limit description length
            f"Type: {issue_data['issuetype']}",
            f"Status: {issue_data['status']}",
            f"Priority: {issue_data['priority']}",
            f"Components: {', '.join(issue_data['components'])}",
            f"Labels: {', '.join(issue_data['labels'])}"
        ]
        
        return "\n".join(components)
    
    def sync_to_chromadb(self, issues: List[Dict], batch_size: int = 100):
        """
        Sync Jira issues to ChromaDB.
        
        Args:
            issues: List of issue dictionaries
            batch_size: Number of issues to process in each batch
        """
        if not issues:
            print("No issues to sync")
            return
        
        print(f"Syncing {len(issues)} issues to ChromaDB...")
        
        # Process in batches to avoid memory issues
        for i in range(0, len(issues), batch_size):
            batch = issues[i:i + batch_size]
            
            # Prepare data for ChromaDB
            ids = [issue["key"] for issue in batch]
            documents = [self._create_searchable_text(issue) for issue in batch]
            metadatas = [
                {
                    "key": issue["key"],
                    "summary": issue["summary"],
                    "description": issue["description"],
                    "status": issue["status"],
                    "issuetype": issue["issuetype"],
                    "created": issue["created"],
                    "updated": issue["updated"],
                    "resolution": issue["resolution"],
                    "priority": issue["priority"],
                    "url": issue["url"],
                    "labels": json.dumps(issue["labels"]),
                    "components": json.dumps(issue["components"])
                }
                for issue in batch
            ]
            
            # Generate embeddings using Google's API (batch request)
            print(f"Generating embeddings for batch {i//batch_size + 1}...")
            result = genai.embed_content(
                model=self.embedding_model_name,
                content=documents,
                task_type="retrieval_document"
            )
            embeddings = result['embedding']

            # Upsert to ChromaDB (updates if exists, inserts if new)
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            
            print(f"Synced batch {i//batch_size + 1}/{(len(issues) + batch_size - 1)//batch_size}")
        
        print(f"Successfully synced {len(issues)} issues to ChromaDB")
        
    def get_collection_stats(self) -> Dict:
        """Get statistics about the ChromaDB collection."""
        count = self.collection.count()
        return {
            "total_issues": count,
            "collection_name": self.collection.name,
            "last_synced": datetime.now().isoformat()
        }


def main():
    parser = argparse.ArgumentParser(description="Sync Jira issues to ChromaDB")
    parser.add_argument(
        "--project",
        default="RHDHBUGS",
        help="Jira project key (default: RHDHBUGS)"
    )
    parser.add_argument(
        "--chroma-dir",
        default=settings.chroma_db_dir,
        help="ChromaDB persistence directory (default: ./chroma_db)"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=1000,
        help="Maximum results per Jira query (default: 1000)"
    )
    parser.add_argument(
        "--embedding-model",
        default="models/text-embedding-004",
        help="Google embedding model (default: models/text-embedding-004)"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize sync
        syncer = JiraChromaSync(
            chroma_persist_directory=args.chroma_dir,
            embedding_model=args.embedding_model
        )
        
        # Fetch issues from Jira
        issues = syncer.fetch_jira_issues(
            project_key=args.project,
            max_results=args.max_results
        )
        
        # Sync to ChromaDB
        syncer.sync_to_chromadb(issues)
        
        # Print stats
        stats = syncer.get_collection_stats()
        print("\n" + "="*50)
        print("Sync completed successfully!")
        print(f"Total issues in ChromaDB: {stats['total_issues']}")
        print(f"Last synced: {stats['last_synced']}")
        print("="*50)
        
    except Exception as e:
        print(f"Error during sync: {e}")
        raise


if __name__ == "__main__":
    main()