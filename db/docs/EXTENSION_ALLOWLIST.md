# PostgreSQL Extension Allow-List

This document defines which PostgreSQL extensions are allowed and under what conditions.

## Allowed Extensions

### pgcrypto

**Purpose**: Encryption functions (if needed)

**Rationale**: Provides cryptographic functions for encryption/decryption if required for sensitive data.

**Where Used**: 
- Column-level encryption (if required)
- Hash functions for data integrity

**Rollback Strategy**: 
- Extensions can be dropped: `DROP EXTENSION IF EXISTS pgcrypto CASCADE;`
- Note: Dropping extension may affect dependent objects

**Environment Policy**: 
- Dev/Staging: Allowed with approval
- Production: Requires Security Lead approval

### uuid-ossp

**Purpose**: UUID generation (if `gen_random_uuid()` not available)

**Rationale**: Provides UUID generation functions. However, PostgreSQL 13+ includes `gen_random_uuid()` natively, so this extension is only needed for older PostgreSQL versions.

**Where Used**: 
- UUID generation for primary keys (if PostgreSQL < 13)

**Rollback Strategy**: 
- Extensions can be dropped: `DROP EXTENSION IF EXISTS "uuid-ossp" CASCADE;`
- Note: If using `uuid_generate_v4()`, must migrate to `gen_random_uuid()` before dropping

**Environment Policy**: 
- **Preference**: Use `gen_random_uuid()` (PostgreSQL 13+) instead of this extension
- Only use if PostgreSQL version < 13

### pg_stat_statements

**Purpose**: Observability (optional, environment-specific)

**Rationale**: Provides query performance statistics for monitoring and optimization.

**Where Used**: 
- Query performance monitoring
- Slow query identification
- Performance optimization

**Rollback Strategy**: 
- Extensions can be dropped: `DROP EXTENSION IF EXISTS pg_stat_statements CASCADE;`
- Note: Dropping extension loses historical statistics

**Environment Policy**: 
- Dev/Staging: Optional, recommended
- Production: Recommended for observability

### btree_gin / btree_gist

**Purpose**: Advanced indexing (when justified)

**Rationale**: Provides GIN/GiST indexes for advanced query patterns (e.g., range queries, full-text search).

**Where Used**: 
- Advanced indexing patterns
- Range queries optimization
- Full-text search (if needed)

**Rollback Strategy**: 
- Extensions can be dropped: `DROP EXTENSION IF EXISTS btree_gin CASCADE;`
- Note: Dropping extension may affect dependent indexes

**Environment Policy**: 
- Requires Backend Lead approval
- Must document use case and performance justification

## Safety Criteria

**All extensions must**:
1. Have documented use case and rationale
2. Include rollback strategy
3. Be approved per environment policy
4. Not introduce security vulnerabilities
5. Be compatible with PostgreSQL 15+

## Environment Policy

**Extensions are created in `public` schema** (default) unless:
- Dedicated schema is required for organizational reasons
- Multi-tenant extension isolation is needed

**Approval Matrix**:
- **Dev/Staging**: Backend Lead approval
- **Production**: Backend Lead + Security Lead approval (for security-sensitive extensions)

## Non-Allow-Listed Extensions

**Any extension not listed here is forbidden** unless:
1. New ADR is created documenting rationale
2. Extension is added to this allow-list
3. Approval is obtained per environment policy

**Rationale**: Restricting extensions prevents ad-hoc use of PostgreSQL features and ensures review of all database-level dependencies.





