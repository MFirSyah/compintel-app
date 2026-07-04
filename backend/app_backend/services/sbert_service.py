"""
SBERT Service untuk pencocokan semantik.
Menggunakan model paraphrase-multilingual-MiniLM-L12-v2.
"""

import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Try to import sentence_transformers
try:
    from sentence_transformers import SentenceTransformer
    SBERT_AVAILABLE = True
except ImportError:
    SBERT_AVAILABLE = False
    logger.warning("⚠️ sentence-transformers not installed. Using fallback similarity.")


class SBERTMatcher:
    """
    SBERT Matcher untuk semantic similarity.
    Menggunakan model paraphrase-multilingual-MiniLM-L12-v2 (384 dimensi).
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self.model = None
        self.embeddings_cache: dict = {}

        if SBERT_AVAILABLE:
            try:
                logger.info(f"🔄 Loading SBERT model: {model_name}")
                self.model = SentenceTransformer(model_name)
                logger.info("✅ SBERT model loaded successfully")
            except Exception as e:
                logger.error(f"❌ Failed to load SBERT model: {e}")
                self.model = None
        else:
            logger.warning("⚠️ SBERT not available, using fallback")

    def encode(self, texts: List[str]) -> Optional[np.ndarray]:
        """Encode texts ke embeddings."""
        if self.model is None:
            return None

        try:
            return self.model.encode(texts, convert_to_numpy=True)
        except Exception as e:
            logger.error(f"❌ Encoding failed: {e}")
            return None

    async def get_embeddings_batch(self, texts: List[str], db) -> np.ndarray:
        """
        Get SBERT embeddings for a list of texts.
        Uses in-memory cache, then DB table 'produk_embeddings', and encodes the rest.
        """
        if self.model is None:
            # Return zero vectors if SBERT is not available
            return np.zeros((len(texts), 384), dtype=np.float32)

        embeddings = [None] * len(texts)
        missing_texts = []
        missing_indices = []

        # 1. Check in-memory cache
        for idx, text in enumerate(texts):
            clean_text = text.strip()
            if clean_text in self.embeddings_cache:
                embeddings[idx] = self.embeddings_cache[clean_text]
            else:
                missing_texts.append(clean_text)
                missing_indices.append(idx)

        if not missing_texts:
            return np.array(embeddings, dtype=np.float32)

        # 2. Check Database for missing texts (batch select)
        from app_backend.models.models import ProductEmbedding
        from sqlalchemy import select, insert
        
        db_found = {}
        try:
            chunk_size = 1000
            for i in range(0, len(missing_texts), chunk_size):
                chunk = missing_texts[i:i+chunk_size]
                stmt = select(ProductEmbedding).where(ProductEmbedding.nama_produk.in_(chunk))
                res = await db.execute(stmt)
                db_rows = res.scalars().all()
                for row in db_rows:
                    if row.embedding_sbert:
                        emb_vec = np.array([float(x) for x in row.embedding_sbert.split(',')], dtype=np.float32)
                        db_found[row.nama_produk] = emb_vec
        except Exception as db_err:
            logger.warning(f"Database SBERT embeddings lookup failed: {db_err}")

        # Update based on DB search
        still_missing_texts = []
        still_missing_indices = []

        for clean_text, orig_idx in zip(missing_texts, missing_indices):
            if clean_text in db_found:
                emb_vec = db_found[clean_text]
                self.embeddings_cache[clean_text] = emb_vec
                embeddings[orig_idx] = emb_vec
            else:
                still_missing_texts.append(clean_text)
                still_missing_indices.append(orig_idx)

        # 3. Encode still missing texts and save to DB
        if still_missing_texts:
            try:
                unique_missing = list(set(still_missing_texts))
                logger.info(f"Encoding {len(unique_missing)} missing SBERT embeddings...")
                encoded = self.model.encode(unique_missing, batch_size=256, show_progress_bar=False, convert_to_numpy=True)
                
                encoded_map = {txt: vec for txt, vec in zip(unique_missing, encoded)}
                
                for clean_text, orig_idx in zip(still_missing_texts, still_missing_indices):
                    emb_vec = encoded_map[clean_text]
                    self.embeddings_cache[clean_text] = emb_vec
                    embeddings[orig_idx] = emb_vec

                # Save new embeddings to DB
                records_to_insert = []
                for txt in unique_missing:
                    vec = encoded_map[txt]
                    serialized = ",".join(map(str, vec.tolist()))
                    records_to_insert.append({
                        "nama_produk": txt,
                        "embedding_sbert": serialized
                    })

                insert_chunk_size = 500
                for i in range(0, len(records_to_insert), insert_chunk_size):
                    chunk = records_to_insert[i:i+insert_chunk_size]
                    try:
                        await db.execute(insert(ProductEmbedding), chunk)
                        await db.commit()
                    except Exception as ins_err:
                        await db.rollback()
                        logger.warning(f"Error saving SBERT embeddings to DB: {ins_err}")
                        # Fallback one by one
                        for rec in chunk:
                            try:
                                await db.execute(insert(ProductEmbedding).values(rec))
                                await db.commit()
                            except Exception:
                                await db.rollback()
            except Exception as e:
                logger.error(f"Batch SBERT encoding or DB cache failed: {e}")
                zero_vec = np.zeros(384, dtype=np.float32)
                for idx in still_missing_indices:
                    if embeddings[idx] is None:
                        embeddings[idx] = zero_vec

        return np.array(embeddings, dtype=np.float32)


    def get_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity antara dua text.
        Returns score antara 0 dan 1.
        """
        # Try SBERT first
        if self.model is not None:
            try:
                embeddings = self.encode([text1, text2])
                if embeddings is not None and len(embeddings) == 2:
                    # Cosine similarity
                    cos_sim = np.dot(embeddings[0], embeddings[1]) / (
                        np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
                    )
                    return float(cos_sim)
            except Exception as e:
                logger.warning(f"SBERT similarity failed: {e}")

        # Fallback: keyword-based similarity
        return self._fallback_similarity(text1, text2)

    def _fallback_similarity(self, text1: str, text2: str) -> float:
        """
        Fallback similarity menggunakan keyword matching.
        Digunakan jika SBERT tidak tersedia.
        """
        # Normalize
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        # Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        jaccard = intersection / union if union > 0 else 0

        # Brand/model matching bonus
        score = jaccard

        # Check for number patterns (model numbers)
        import re
        nums1 = set(re.findall(r'\d+[a-z]*|\d+', text1.lower()))
        nums2 = set(re.findall(r'\d+[a-z]*|\d+', text2.lower()))

        if nums1 and nums2:
            num_overlap = len(nums1 & nums2) / len(nums1 | nums2)
            score = (score * 0.7) + (num_overlap * 0.3)

        return min(1.0, max(0.0, score))

    def search(self, query: str, corpus: List[str], top_k: int = 10) -> List[dict]:
        """
        Search corpus dengan semantic similarity.
        Returns list of {index, text, score}.
        """
        if not corpus:
            return []

        if self.model is not None:
            try:
                # Encode query and corpus
                query_emb = self.encode([query])
                corpus_embs = self.encode(corpus)

                if query_emb is None or corpus_embs is None:
                    return self._fallback_search(query, corpus, top_k)

                # Calculate similarities
                results = []
                for i, corpus_emb in enumerate(corpus_embs):
                    similarity = float(np.dot(query_emb[0], corpus_emb) / (
                        np.linalg.norm(query_emb[0]) * np.linalg.norm(corpus_emb)
                    ))
                    results.append({
                        'index': i,
                        'text': corpus[i],
                        'score': similarity
                    })

                # Sort by score descending
                results.sort(key=lambda x: x['score'], reverse=True)
                return results[:top_k]

            except Exception as e:
                logger.warning(f"SBERT search failed: {e}")

        return self._fallback_search(query, corpus, top_k)

    def _fallback_search(self, query: str, corpus: List[str], top_k: int) -> List[dict]:
        """Fallback search using keyword matching."""
        results = []
        for i, text in enumerate(corpus):
            score = self._fallback_similarity(query, text)
            results.append({
                'index': i,
                'text': text,
                'score': score
            })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]
