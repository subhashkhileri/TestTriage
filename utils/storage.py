from google.cloud import storage
from typing import List, Set
from config.settings import settings

class StorageClient:
    """Google Cloud Storage client for accessing test artifacts."""
    
    def __init__(self):
        self.client = storage.Client.create_anonymous_client()
        self.bucket = self.client.bucket(settings.GCS_BUCKET_NAME)
    
    def get_text_from_blob(self, prefix: str) -> str:
        """Get text content from a blob."""
        try:
            return self.bucket.blob(prefix).download_as_text()
        except Exception as e:
            return f"Error getting text from file: {e}"
    
    def get_bytes_from_blob(self, prefix: str) -> bytes:
        """Get bytes content from a blob."""
        return self.bucket.blob(prefix).download_as_bytes()
    
    def blob_exists(self, prefix: str) -> bool:
        """Check if a blob exists."""
        return self.bucket.blob(prefix).exists()
    
    def list_blobs(self, prefix: str) -> List[str]:
        """List all blob names with the given prefix."""
        return [blob.name for blob in self.bucket.list_blobs(prefix=prefix)]
    
    def get_immediate_directories(self, prefix: str) -> List[str]:
        """Get immediate directories from a given prefix path."""
        dirs: Set[str] = set()
        for blob in self.bucket.list_blobs(prefix=prefix):
            # Get the part after the prefix
            relative_path = blob.name[len(prefix):]
            # Only get the first directory name (before any slash)
            if relative_path and '/' in relative_path:
                dir_name = relative_path.split('/')[0]
                dirs.add(dir_name)
        
        return sorted(list(dirs))
    
    def get_immediate_files(self, prefix: str) -> List[str]:
        """Get immediate files from a given prefix path (not in subdirectories)."""
        files: Set[str] = set()
        for blob in self.bucket.list_blobs(prefix=prefix):
            # Get the part after the prefix
            relative_path = blob.name[len(prefix):]
            # Only get files that don't have any slashes (immediate files)
            if relative_path and '/' not in relative_path:
                files.add(relative_path)
        
        return sorted(list(files))

# Global storage client instance
storage_client = StorageClient() 