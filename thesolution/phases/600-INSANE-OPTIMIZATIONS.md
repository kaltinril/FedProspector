# Phase 600: Insane Optimizations

**Status:** DEFERRED
**Priority:** Low — only revisit when scale justifies it

## Purpose

Parking lot for optimizations that are technically sound but not worth the effort at current scale (~26K documents, ~500K intel evidence rows). Revisit when row counts hit millions or performance becomes a bottleneck.

## Ideas

### 1. Binary hash storage

**Current:** `content_hash` and `text_hash` stored as `CHAR(64)` hex strings.
**Optimization:** Store as `BINARY(32)` — same SHA-256 hash, half the storage, faster comparisons.
**Savings:** ~800KB per index at 26K rows. Negligible now, meaningful at 1M+ rows.
**Effort:** Schema migration + update all Python code that reads/writes hashes (hex encode/decode at application boundary).

### 2. Hash prefix indexes

**Current:** Full 64-char index on hash columns.
**Optimization:** Index only the first 8-12 hex characters. At 8 chars, collision probability is ~1 in 4 billion — practically unique at any realistic scale.
**Savings:** Smaller index footprint, fits in memory longer as table grows.
**Effort:** One ALTER TABLE per hash column.

### 3. Non-cryptographic hashing for dedup

**Current:** SHA-256 (cryptographic, computationally expensive).
**Optimization:** Use xxHash (XXH3) for dedup hashes — 20-50x faster computation. Keep SHA-256 only where cryptographic properties matter (if anywhere).
**Savings:** Faster hash computation during download/extraction. Currently negligible since PDF parsing dominates, but would matter if processing thousands of files per batch.
**Effort:** Add xxhash dependency, migration to recompute all hashes.
