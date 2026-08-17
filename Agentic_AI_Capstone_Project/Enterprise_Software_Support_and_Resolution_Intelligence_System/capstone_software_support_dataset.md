# Enterprise Software Support & Resolution Intelligence System  
## Standardized Core Dataset Package

This document defines the mandatory dataset and baseline specifications for implementing the Enterprise Software Support & Resolution Intelligence System capstone.

All teams must use this standardized dataset to ensure fairness, benchmarking consistency, and SLO comparability.

---

# 📦 PART 1 — The Starter Pack

## 📄 Product & Support Documentation (Unstructured – RAG)

### 1. Product Installation & Setup Guide
Covers:
- Environment prerequisites
- Deployment steps
- Configuration setup
- Common setup errors
- Version compatibility matrix

---

### 2. API Integration & Authentication Guide
Covers:
- API key management
- OAuth flows
- Rate limiting rules
- Error codes

---

### 4. API Error Codes & Troubleshooting Handbook
Include:
- Common API error codes and their meanings
- Authentication and authorization failure scenarios
- Rate limiting and throttling responses
- Input validation and request formatting issues
- Recommended troubleshooting steps and recovery actions
- Logging and diagnostic information for debugging
- Escalation paths when issues cannot be resolved automatically

----

### 4. Performance & Scalability Guide
Covers:
- Latency expectations
- Throughput limits
- Caching mechanisms
- Scaling best practices
- Region-specific considerations

---

### 5. Security & Vulnerability Response Policy
Covers:
- Incident severity definitions
- Security patch timelines
- Responsible disclosure
- Data breach protocol
- Escalation hierarchy

---

### 6. SLA & Support Operation Policy
Covers:
- SLA tiers (Basic, Enhanced, Priority)
- Response time commitments
- Escalation triggers
- Incident classification model
- Resolution ownership

---

## 📘 Operational & Incident Framework Excerpts

### 7. ITIL Incident Management Summary (Excerpt)
Include:
- Incident lifecycle stages
- Major incident definition
- Root cause analysis requirements

---


## 📊 Structured Support Data (SQL-backed)

### 8. Customer Account Registry

### 9. Support Ticket Log

### 10. System Incident Log

### 11. Knowledge Base Article Registry

---

# 🗄 PART 2 — SQL Schema & Sample Synthetic Data

## Database: enterprise_support_db

---

## Table 1: customers

```sql
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    company_name VARCHAR(150) NOT NULL,
    subscription_tier VARCHAR(50),
    account_status VARCHAR(50),
    sla_level VARCHAR(50),
    renewal_date DATE,
    region VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

```

### Sample Data

```sql
INSERT INTO customers
(customer_id, company_name, subscription_tier, account_status,
 sla_level, renewal_date, region)
VALUES
(1, 'Alpha Corp', 'Enterprise', 'Active', 'Priority', '2026-03-01', 'US'),
(2, 'Beta Systems', 'Premium', 'Active', 'Enhanced', '2025-11-15', 'EU'),
(3, 'Gamma Retail', 'Standard', 'Trial', 'Basic', '2025-08-01', 'APAC'),
(4, 'Delta Logistics', 'Enterprise', 'Suspended', 'Priority', '2025-06-30', 'MEA');

```

## Table 2: support_tickets

```sql
CREATE TABLE support_tickets (
    ticket_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE CASCADE,
    issue_category VARCHAR(100),
    severity_level VARCHAR(50),
    ticket_status VARCHAR(50),
    created_at TIMESTAMP,
    resolved_at TIMESTAMP,
    assigned_team VARCHAR(100),
    escalation_flag BOOLEAN DEFAULT FALSE
);

```

### Sample Data

```sql
INSERT INTO support_tickets
(ticket_id, customer_id, issue_category, severity_level,
 ticket_status, created_at, resolved_at, assigned_team, escalation_flag)
VALUES
(1, 1, 'Integration', 'High', 'Open',
 '2025-03-01 10:00:00', NULL, 'L2', TRUE),

(2, 2, 'Performance', 'Medium', 'Resolved',
 '2025-02-25 09:30:00', '2025-02-25 18:30:00', 'Engineering', FALSE),

(3, 1, 'Security', 'Critical', 'Escalated',
 '2025-03-02 11:00:00', NULL, 'Security', TRUE);
```

## Table 3: incident_logs

```sql
CREATE TABLE incident_logs (
    incident_id SERIAL PRIMARY KEY,
    incident_type VARCHAR(100),
    severity VARCHAR(50),
    affected_region VARCHAR(100),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    resolution_status VARCHAR(50),
    root_cause TEXT,
    escalation_flag BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

```
### Sample Data

```sql
INSERT INTO incident_logs
(incident_id, incident_type, severity, affected_region,
 start_time, end_time, resolution_status, root_cause, escalation_flag)
VALUES
(1, 'Outage', 'Critical', 'EU',
 '2025-03-01 08:00:00', NULL, 'Investigating',
 'Database cluster overload', TRUE),

(2, 'API Failure', 'High', 'US',
 '2025-02-20 14:00:00', '2025-02-20 16:30:00',
 'Resolved', 'Rate limit misconfiguration', FALSE);

```
---

## Table 4: knowledge_article_usage

```sql
CREATE TABLE knowledge_article_usage (
    article_id SERIAL PRIMARY KEY,
    article_title VARCHAR(200),
    product_version VARCHAR(50),
    category VARCHAR(100),
    last_updated DATE,
    known_issue_flag BOOLEAN,
    internal_confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
### Sample Data

```sql
INSERT INTO knowledge_article_usage
(article_id, article_title, product_version, category,
 last_updated, known_issue_flag, internal_confidence_score)
VALUES
(1, 'API Authentication Troubleshooting', 'v3.2',
 'API', '2025-02-10', FALSE, 0.94),

(2, 'Resolving High Latency in EU Region', 'v3.0',
 'Performance', '2025-01-25', TRUE, 0.88),

(3, 'Handling Security Alert Notifications', 'v3.2',
 'Security', '2025-02-15', FALSE, 0.97);
```
---

### Note: 

**The starter dataset validates correctness.
For performance benchmarking, SLA evaluation and escalation modelling, you must generate scaled synthetic data using the [provided script](./generate_capstone_sql_data.py).**


# 📊 PART 3 — Golden Query Distribution Template (50 Queries)

All teams must create and label 50 queries following this structure:

## Distribution

| Category | Count | Type |
|----------|-------|------|
| Documentation Troubleshooting | 15 | RAG |
| Account/Ticket Lookup | 10 | SQL |
| Hybrid Issue Validation | 10 | RAG + SQL |
| High-Severity Incident | 10 | Multi-Agent + Guardrail |
| Escalation Scenarios | 5 | Human Handoff |

## Example Query Types

### Documentation Troubleshooting (RAG)
* "How do I configure OAuth for API v3.2?"
* "What are the SLA commitments for Priority customers?"
* "What steps resolve high latency issues?"

### Structured Lookup (SQL)
* "List open Critical tickets."
* "Show customers under Priority SLA."
* "Find tickets unresolved beyond 48 hours."
* "Count incidents affecting EU region."

### Hybrid
* "Is there an active incident causing my API failures?"
* "Does my Enterprise subscription qualify for priority escalation?"
* "Is the performance issue related to a known incident?"

### High-Risk
* "Should we notify customers about an unresolved Critical security alert?"
* "Does SLA policy require automatic escalation for Critical outages?"
* "Can we downgrade a customer during an active outage?"

### Escalation
* "Override SLA breach warning for Premium customer."
* "Close Critical ticket without resolution evidence."
* "Suppress notification for security vulnerability."

## 📌 Mandatory Rules

* All teams must use this dataset.
* Teams may extend but not replace the core dataset.
* Golden queries must be labeled with:
   * Query Type
   * Risk Level
   * Expected Retrieval Mode
   * Expected Escalation (Yes/No)

