import os
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
import hnswlib
import torch
from sklearn.metrics.pairwise import cosine_similarity

class VectorDB:
    _model_cache = {}  # Class variables for cache models

    def __init__(self, model_name='BAAI/bge-large-en-v1.5', model_cache_dir=None, similarity_threshold=0.85):
        """Initializing vector database tool class"""
        self.model_name = model_name
        self.model_cache_dir = model_cache_dir or os.path.join(os.path.dirname(__file__), "model_cache")
        os.makedirs(self.model_cache_dir, exist_ok=True)

        # Load Model from Cache
        self.model = self._load_or_create_model()
        self.index = None
        self.documents = []
        self.embeddings_cache = []  # Cache vector for existing documents
        self.similarity_threshold = similarity_threshold  # Similarity threshold over which repetition is considered
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", ",", " ", ""]
        )
        self.init_idex = []

    def _load_or_create_model(self):
        """Load the model from the cache and create the cache if it does not exist"""
        # Prioritize the use of environmental variables BGE_MODEL_L，Use if not self.model_name
        model_name_to_use = os.getenv("BGE_MODEL_L") or self.model_name

        # Print hints if environment variables are used
        if os.getenv("BGE_MODEL_L"):
            print(f"Using model from environment variable BGE_MODEL_L: {model_name_to_use}")

        # Check for models in the class cache
        if model_name_to_use in VectorDB._model_cache:
            print(f"Loading model from memory cache: {model_name_to_use}")
            return VectorDB._model_cache[model_name_to_use]

        # Check Disk Cache
        cache_path = os.path.join(self.model_cache_dir, model_name_to_use.replace('/', '_'))
        if os.path.exists(cache_path):
            print(f"Loading model from disk cache: {cache_path}")
            model = SentenceTransformer(cache_path)
        else:
            print(f"Loading model for the first time: {model_name_to_use}")
            model = SentenceTransformer(model_name_to_use)
            # Save to disk cache
            model.save(cache_path)
            print(f"Model saved to: {cache_path}")

        # Add to Memory Cache
        VectorDB._model_cache[model_name_to_use] = model
        return model

    def encode(self, texts):
        """Encoding using local models"""
        if not texts:
            return np.array([])
        return self.model.encode(texts, normalize_embeddings=True)

    def _is_duplicate(self, new_embedding, existing_embeddings, threshold=None):
        """Check if new vectors duplicate existing vectors"""
        if threshold is None:
            threshold = self.similarity_threshold

        # Validate the input before comparing embeddings.
        if existing_embeddings is None or len(existing_embeddings) == 0:
            return False, -1

        # Ensure numpy Array
        existing_embs = np.array(existing_embeddings)
        # If an index is available and the amount of data is larger, use the index to query the nearest neighbour
        try:
            if self.index is not None:
                ids, distances = self.index.knn_query(new_embedding.reshape(1, -1), k=1)
                idx = int(ids[0][0])
                sim = 1.0 - float(distances[0][0])  # hnswlib cosine distance -> similarity
                return (sim > threshold), idx
        except Exception:
            # If an index query is wrong, back to exact calculation
            pass

        # Accurate calculation (applies to small scale or index when not available)）
        similarities = cosine_similarity([new_embedding], existing_embs)[0]
        max_similarity = float(np.max(similarities))
        max_index = int(np.argmax(similarities))

        return max_similarity > threshold, max_index

    def _remove_duplicates_from_embeddings(self, embeddings, documents, threshold=None):
        """Remove duplicate entries from the embedded vector list"""
        if threshold is None:
            threshold = self.similarity_threshold

        if len(embeddings) <= 1:
            return embeddings, documents

        unique_embeddings = []
        unique_documents = []
        duplicate_count = 0

        for i, (embedding, doc) in enumerate(zip(embeddings, documents)):
            is_dup, _ = self._is_duplicate(embedding, unique_embeddings, threshold)

            if not is_dup:
                unique_embeddings.append(embedding)
                unique_documents.append(doc)
            else:
                duplicate_count += 1

        if duplicate_count > 0:
            print(f"Removed {duplicate_count} duplicate text chunks")

        return np.array(unique_embeddings), unique_documents

    def create_from_text(self, text: str, metadata: dict = None, init: bool = False, enable_dedup: bool = True, allow_split: bool = True):  # fix: Increase allow_split Parameters
        """
        Create vector database from text or add text to existing vector database

        Args:
            text: Enter Text
            metadata: Metadata
            init: Whether to store the initial index for subsequent deletion operations
            enable_dedup: Whether to enable intelligence to weigh
            allow_split: Whether to split long text (default) True）

        Returns:
            int: Number of documents actually added
        """
        if not text or text.strip() == "":
            print("Warning: Vector database input text is empty")
            return 0

        # Text segments (optional)）
        if allow_split:
            texts = self.text_splitter.split_text(text)
        else:
            texts = [text]
        if not texts:
            print("Warning: Text after block is empty")
            return 0

        # Create for each text block Documents Object
        docs = []
        for i, text_chunk in enumerate(texts):
            chunk_metadata = {"chunk_id": len(self.documents) + i}
            if metadata:
                chunk_metadata.update(metadata)
            doc = Document(page_content=text_chunk, metadata=chunk_metadata)
            docs.append(doc)

        # Use local model encoding
        embeddings = self.encode([doc.page_content for doc in docs])

        if enable_dedup:
            # Remove duplication with existing documents
            if len(self.embeddings_cache) > 0:
                final_embeddings = []
                final_docs = []
                duplicate_count = 0

                for embedding, doc in zip(embeddings, docs):
                    is_dup, dup_index = self._is_duplicate(embedding, self.embeddings_cache)

                    if not is_dup:
                        final_embeddings.append(embedding)
                        final_docs.append(doc)
                    else:
                        duplicate_count += 1
                        print(f"Found a duplicate document; similarity to existing document {dup_index} is too high")

                if duplicate_count > 0:
                    print(f"Deduplicated against existing documents; removed {duplicate_count} duplicate text chunks")

                embeddings = np.array(final_embeddings)
                docs = final_docs

        if len(embeddings) == 0:
            print("All text blocks are identified as duplicates and no content added")
            return 0

        # Create HNSW Index
        dimension = embeddings.shape[1]
        if self.index is None:
            self.index = hnswlib.Index(space='cosine', dim=dimension)
            self.index.init_index(max_elements=10000, ef_construction=200, M=16)

        # Add Vector to Index
        start_idx = len(self.documents)
        ids = np.arange(start_idx, start_idx + len(embeddings))
        self.index.add_items(embeddings, ids)

        # Save Document and Vector Cache
        self.documents.extend(docs)
        self.embeddings_cache.extend(embeddings.tolist())

        # Record initial index
        if init:
            for i in range(start_idx, start_idx + len(embeddings)):
                self.init_idex.append(i)

        print(f"Added {len(docs)} text chunks to the vector database")
        return len(docs)

    def search(self, query, k=3):
        """
        input: str
        output: list of Document
        Search for most similar documents in vector databases
        """
        if self.index is None or not self.documents:
            print("Warning: Vector database is empty")
            return []

        if query == "":
            print("Warning: Query string is empty")
            return []

        # Encoding queries
        query_vector = self.encode([query])

        # Search
        ids, distances = self.index.knn_query(query_vector, k=min(k, len(self.documents)))

        # Return Result
        results = []
        for idx in ids[0]:
            if 0 <= idx < len(self.documents):
                results.append(self.documents[idx])

        return results


    def save(self, path):
        """Save vector database"""
        # Create Directory(If not present)
        os.makedirs(path, exist_ok=True)

        # Save Document
        docs_path = os.path.join(path, "documents.pkl")
        with open(docs_path, "wb") as f:
            pickle.dump(self.documents, f)

        # Save embedded vector cache
        embeddings_path = os.path.join(path, "embeddings_cache.pkl")
        with open(embeddings_path, "wb") as f:
            pickle.dump(self.embeddings_cache, f)

        # Save Initial Index
        init_index_path = os.path.join(path, "init_index.pkl")
        with open(init_index_path, "wb") as f:
            pickle.dump(self.init_idex, f)

        # Save Profile Information
        config_path = os.path.join(path, "config.pkl")
        config = {
            "model_name": self.model_name,
            "similarity_threshold": self.similarity_threshold,
            "has_index": self.index is not None
        }

        if self.index is not None:
            # Save Index
            index_path = os.path.join(path, "index.bin")
            self.index.save_index(index_path)

            # Add Index Related Configuration
            config.update({
                "dim": self.index.dim,
                "space": "cosine",
                "max_elements": self.index.get_max_elements()
            })

        with open(config_path, "wb") as f:
            pickle.dump(config, f)

        if self.index is None:
            print(f"Empty vector database saved to: {path}")
        else:
            print(f"Vector database saved to: {path}")
        return True

    def load(self, path):
        """Load vector database"""
        if not os.path.exists(path):
            raise ValueError(f"Path does not exist: {path}")

        docs_path = os.path.join(path, "documents.pkl")
        config_path = os.path.join(path, "config.pkl")
        embeddings_path = os.path.join(path, "embeddings_cache.pkl")
        init_index_path = os.path.join(path, "init_index.pkl")

        # Check necessary files
        required_files = [docs_path, config_path]
        if not all(os.path.exists(p) for p in required_files):
            raise ValueError(f"Required files are missing from {path}")

        # Load Configuration
        with open(config_path, "rb") as f:
            config = pickle.load(f)

        # Load Document
        with open(docs_path, "rb") as f:
            self.documents = pickle.load(f)

        # Load embedded vector cache (if available)）
        if os.path.exists(embeddings_path):
            with open(embeddings_path, "rb") as f:
                self.embeddings_cache = pickle.load(f)
        else:
            self.embeddings_cache = []

        # Load initial index (if any)）
        if os.path.exists(init_index_path):
            with open(init_index_path, "rb") as f:
                self.init_idex = pickle.load(f)
        else:
            self.init_idex = []

        # Update Model Configuration
        if "model_name" in config:
            self.model_name = config["model_name"]
        if "similarity_threshold" in config:
            self.similarity_threshold = config["similarity_threshold"]

        # Load Index (if available)）
        if config.get("has_index", False):
            index_path = os.path.join(path, "index.bin")
            if os.path.exists(index_path):
                # Initialise Indexing
                self.index = hnswlib.Index(space=config["space"], dim=config["dim"])
                self.index.load_index(index_path, max_elements=config["max_elements"])
            else:
                print("Warning: Configure the index shown but the index file does not exist, the index is recreated")
                self.index = None
        else:
            self.index = None

        # Recreate the index if there is a document but no index
        if self.documents and self.index is None:
            print("Document detected but not indexed, recreated...")
            if not self.embeddings_cache:
                # Recalculate embedded vector
                all_texts = [doc.page_content for doc in self.documents]
                self.embeddings_cache = self.encode(all_texts).tolist()

            # Rebuild Index
            if self.embeddings_cache:
                embeddings = np.array(self.embeddings_cache)
                dimension = embeddings.shape[1]
                self.index = hnswlib.Index(space='cosine', dim=dimension)
                self.index.init_index(max_elements=max(10000, len(embeddings)),
                                    ef_construction=200, M=16)
                self.index.add_items(embeddings, np.arange(len(embeddings)))

        # Recalculate if no embedded vector cache exists
        if self.documents and not self.embeddings_cache:
            all_texts = [doc.page_content for doc in self.documents]
            self.embeddings_cache = self.encode(all_texts).tolist()

        if self.documents:
            print(f"Loaded vector database from {path} with {len(self.documents)} documents")
        else:
            print(f"Loaded empty vector database from {path}")
        return True

    def delete_documents(self):
        """Delete the specified document"""
        if not self.init_idex or not self.documents:
            return False

        # Filter the document to keep and the corresponding document ID
        new_documents = []
        for i, doc in enumerate(self.documents):
            if i not in self.init_idex:
                new_documents.append(doc)

        # Rebuild Index
        if new_documents:
            all_embeddings = self.encode([doc.page_content for doc in new_documents])
            dimension = all_embeddings.shape[1]

            # Create a new index
            self.index = hnswlib.Index(space='cosine', dim=dimension)
            self.index.init_index(max_elements=max(10000, len(all_embeddings)),
                             ef_construction=200, M=16)
            self.index.add_items(all_embeddings, np.arange(len(all_embeddings)))

        # Update List of Documents
        self.documents = new_documents
        self.init_idex = []
        return True

    def deduplicate_database(self, threshold=None):
        """Reload the entire database"""
        if threshold is None:
            threshold = self.similarity_threshold

        if len(self.documents) <= 1:
            print("There are not enough documents in the database to weigh them")
            return 0

        print(f"Starting database deduplication; current document count: {len(self.documents)}")

        # Recalculate the embedded vector of all documents
        all_texts = [doc.page_content for doc in self.documents]
        all_embeddings = self.encode(all_texts)

        # Execute Heavy
        unique_embeddings, unique_documents = self._remove_duplicates_from_embeddings(
            all_embeddings, self.documents, threshold
        )

        removed_count = len(self.documents) - len(unique_documents)

        if removed_count > 0:
            # Rebuild Index
            dimension = unique_embeddings.shape[1]
            self.index = hnswlib.Index(space='cosine', dim=dimension)
            self.index.init_index(max_elements=max(10000, len(unique_embeddings)),
                                ef_construction=200, M=16)
            self.index.add_items(unique_embeddings, np.arange(len(unique_embeddings)))

            # Update document list and cache
            self.documents = unique_documents
            self.embeddings_cache = unique_embeddings.tolist()

            # Update Initial Index
            if self.init_idex:
                # Simple processing: Empty initial index because index has been changed
                print("Warning: Initial index has been reset after restarting")
                self.init_idex = []

            print(f"Deduplication complete; removed {removed_count} duplicate documents; current document count: {len(self.documents)}")
        else:
            print("No duplicate documents found")

        return removed_count

    def set_similarity_threshold(self, threshold):
        """Set a similarity threshold"""
        if 0.0 <= threshold <= 1.0:
            self.similarity_threshold = threshold
            print(f"Similarity threshold set to: {threshold}")
        else:
            print("Similarity threshold must be 0.0 Present 1.0 Between")

    def get_similarity_matrix(self, top_k=10):
        """Get the most similar document pairs for debugging and analysing"""
        if len(self.embeddings_cache) < 2:
            return []

        embeddings = np.array(self.embeddings_cache)
        similarity_matrix = cosine_similarity(embeddings)

        # Get the most similar document pair
        similar_pairs = []
        for i in range(len(similarity_matrix)):
            for j in range(i + 1, len(similarity_matrix)):
                similarity = similarity_matrix[i][j]
                similar_pairs.append({
                    'doc1_index': i,
                    'doc2_index': j,
                    'similarity': similarity,
                    'doc1_content': self.documents[i].page_content[:100] + "...",
                    'doc2_content': self.documents[j].page_content[:100] + "..."
                })

        # Sort by Similarity and Return Before k individual
        similar_pairs.sort(key=lambda x: x['similarity'], reverse=True)
        return similar_pairs[:top_k]
