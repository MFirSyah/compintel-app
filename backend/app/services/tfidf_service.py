"""
TF-IDF Service untuk pencocokan karakter n-gram.
Menggunakan char_wb analyzer dengan n-gram range (2, 3).
"""

import logging
from typing import List, Dict, Tuple
import numpy as np
from collections import Counter
import re

logger = logging.getLogger(__name__)


class TFIDFMatcher:
    """
    TF-IDF Matcher menggunakan character n-gram cosine similarity.
    Konfigurasi sesuai BRIEF_SKRIPSI_MU_FIRMAN:
    - analyzer: char_wb (character n-gram dengan word boundaries)
    - ngram_range: (2, 3)
    - max_features: 15000
    """

    def __init__(self):
        self.config = {
            'analyzer': 'char_wb',
            'ngram_range': (2, 3),
            'max_features': 15000,
            'min_df': 2
        }
        self.corpus_vectors: Dict[str, np.ndarray] = {}
        self.corpus_terms: Dict[str, List[str]] = {}
        logger.info("✅ TFIDFMatcher initialized")

    def preprocess(self, text: str) -> str:
        """Clean dan normalize text."""
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def get_char_ngrams(self, text: str, n: int) -> List[str]:
        """Extract character n-grams dari text."""
        text = self.preprocess(text)
        if len(text) < n:
            return [text] if text else []
        return [text[i:i+n] for i in range(len(text) - n + 1)]

    def get_ngrams(self, text: str) -> List[str]:
        """Get bigrams dan trigrams."""
        bigrams = self.get_char_ngrams(text, 2)
        trigrams = self.get_char_ngrams(text, 3)
        return bigrams + trigrams

    def vectorize(self, texts: List[str]) -> Tuple[np.ndarray, List[str]]:
        """
        Vectorize list of texts menggunakan TF-IDF.
        Returns: (tfidf_matrix, feature_names)
        """
        if not texts:
            return np.array([]), []

        # Collect all n-grams
        all_ngrams = []
        for text in texts:
            ngrams = self.get_ngrams(text)
            all_ngrams.extend(ngrams)

        # Build vocabulary (unique n-grams)
        term_freq = Counter(all_ngrams)
        vocab = {term: idx for idx, term in enumerate(term_freq.keys())}
        feature_names = list(vocab.keys())

        # Build TF-IDF matrix
        tfidf_matrix = np.zeros((len(texts), len(vocab)))

        for i, text in enumerate(texts):
            ngrams = self.get_ngrams(text)
            ngram_counts = Counter(ngrams)

            for ngram, count in ngram_counts.items():
                if ngram in vocab:
                    # TF (term frequency)
                    tf = count / len(ngrams) if len(ngrams) > 0 else 0
                    # IDF (simplified - document frequency)
                    doc_count = sum(1 for t in texts if ngram in self.preprocess(t))
                    idf = np.log(len(texts) / (doc_count + 1)) + 1
                    tfidf_matrix[i, vocab[ngram]] = tf * idf

        return tfidf_matrix, feature_names

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity antara dua vektor."""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def add_corpus(self, corpus: List[str]):
        """Tambahkan corpus untuk indexing."""
        for i, text in enumerate(corpus):
            self.corpus_vectors[f"doc_{i}"] = text

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Search corpus dengan query.
        Returns list of (doc_index, similarity_score).
        """
        if not self.corpus_vectors:
            return []

        # Vectorize query
        query_clean = self.preprocess(query)
        query_ngrams = self.get_ngrams(query_clean)

        results = []
        for doc_id, text in self.corpus_vectors.items():
            doc_ngrams = self.get_ngrams(text)

            # Calculate TF-IDF similarity
            all_terms = list(set(query_ngrams + doc_ngrams))

            if not all_terms:
                continue

            # Build frequency vectors
            query_freq = Counter(query_ngrams)
            doc_freq = Counter(doc_ngrams)

            # Calculate cosine similarity
            dot_product = sum(query_freq.get(t, 0) * doc_freq.get(t, 0) for t in all_terms)
            query_norm = np.sqrt(sum(v**2 for v in query_freq.values()))
            doc_norm = np.sqrt(sum(v**2 for v in doc_freq.values()))

            if query_norm > 0 and doc_norm > 0:
                similarity = dot_product / (query_norm * doc_norm)
                results.append({
                    'doc_id': doc_id,
                    'text': text,
                    'score': float(similarity)
                })

        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[:top_k]

    def get_similarity(self, query: str, target: str) -> float:
        """Get similarity score antara query dan target text."""
        query_clean = self.preprocess(query)
        target_clean = self.preprocess(target)

        query_ngrams = self.get_ngrams(query_clean)
        target_ngrams = self.get_ngrams(target_clean)

        all_terms = list(set(query_ngrams + target_ngrams))
        if not all_terms:
            return 0.0

        query_freq = Counter(query_ngrams)
        target_freq = Counter(target_ngrams)

        dot_product = sum(query_freq.get(t, 0) * target_freq.get(t, 0) for t in all_terms)
        query_norm = np.sqrt(sum(v**2 for v in query_freq.values()))
        target_norm = np.sqrt(sum(v**2 for v in target_freq.values()))

        if query_norm > 0 and doc_norm := target_norm:
            return float(dot_product / (query_norm * doc_norm))
        return 0.0

