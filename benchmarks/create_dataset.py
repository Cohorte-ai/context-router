"""Create a realistic enterprise document collection + labeled evaluation dataset.

Generates:
1. benchmarks/data/documents/ — 30 enterprise documents across 5 domains
2. benchmarks/data/queries.json — 60 queries with ground-truth relevance labels
3. benchmarks/data/routes_ground_truth.json — expected route matches per query
4. benchmarks/data/permissions_ground_truth.json — expected access decisions

The ground truth is hand-crafted, not system-generated.
"""

from __future__ import annotations

import json
from pathlib import Path

DOCS_DIR = Path("benchmarks/data/documents")
DATA_DIR = Path("benchmarks/data")


def create_documents() -> dict[str, str]:
    """Create 30 enterprise documents across 5 domains. Returns {path: content}."""
    docs: dict[str, str] = {}

    # === HR / Policies (6 docs) ===
    docs["hr/remote-work-policy.md"] = """# Remote Work Policy

## Eligibility
All full-time employees who have completed their 90-day probationary period are eligible
for remote work. Part-time employees and contractors require manager approval.

## Schedule
Remote employees must maintain core hours from 10 AM to 3 PM in their local timezone.
Flexible scheduling outside core hours is permitted with manager approval.

## Equipment
The company provides a laptop and external monitor. Employees must maintain a reliable
internet connection with minimum 25 Mbps download speed. IT support is available for
home office setup via the IT helpdesk portal.

## Communication
Slack is the primary communication tool. All team meetings must be attended via video call.
Response time expectation during core hours is 30 minutes for Slack messages.
"""

    docs["hr/expense-policy.md"] = """# Expense Policy

## Travel
Economy-class flights for domestic travel. Business class permitted for international
flights over 6 hours. Hotels should not exceed $200 per night in standard markets
or $300 in high-cost cities (NYC, SF, London).

## Meals
Daily meal allowance: $75 domestic, $100 international. Client entertainment over
$500 requires pre-approval from department head.

## Software
Individual software under $100/month does not need approval. Team-wide subscriptions
require department head sign-off. All software must be vetted by IT security.

## Reimbursement
Submit expense reports within 30 days. Reimbursements processed bi-weekly on the
1st and 15th. Late submissions (over 60 days) require VP approval.
"""

    docs["hr/onboarding-guide.md"] = """# Employee Onboarding Guide

## First Week
- Day 1: IT setup, badge access, security training
- Day 2: Meet your team, 1:1 with manager
- Day 3: Product overview and architecture walkthrough
- Day 4: Development environment setup
- Day 5: First small task assignment

## First Month
Complete all mandatory training modules in the LMS. Set up your OKRs with your manager.
Schedule coffee chats with at least 5 people outside your team.

## Benefits Enrollment
Complete benefits enrollment within 30 days of start date. Health, dental, and vision
insurance begins on the first of the month following your start date.
"""

    docs["hr/pto-policy.md"] = """# PTO Policy

## Annual Allowance
Full-time employees receive 20 days of PTO per year, accrued monthly. After 3 years
of service, this increases to 25 days. After 7 years, 30 days.

## Requesting Time Off
Submit PTO requests at least 2 weeks in advance for planned vacations. Emergency and
sick days do not require advance notice but should be reported by 9 AM.

## Holidays
The company observes 10 federal holidays per year. The office is closed on these days.

## Carryover
Up to 5 unused PTO days can be carried over to the next calendar year. Days beyond
5 are forfeited on December 31.
"""

    docs["hr/compensation-structure.md"] = """# Compensation Structure

## Salary Bands
Engineering: L3 ($120K-$160K), L4 ($150K-$200K), L5 ($190K-$260K), L6 ($250K-$350K)
Product: PM1 ($110K-$150K), PM2 ($140K-$190K), PM3 ($180K-$250K)
Design: D1 ($100K-$140K), D2 ($130K-$175K), D3 ($165K-$230K)

## Equity
All full-time employees receive stock options. Vesting is 4 years with a 1-year cliff.
Refresh grants are awarded annually based on performance.

## Bonus
Annual performance bonus of 10-20% of base salary based on individual and company performance.
Bonus is paid in Q1 of the following year.
"""

    docs["hr/code-of-conduct.md"] = """# Code of Conduct

## Core Values
Integrity, respect, collaboration, and continuous improvement guide all our interactions.

## Workplace Behavior
Harassment, discrimination, and retaliation are strictly prohibited. Report concerns
to HR or use the anonymous ethics hotline at 1-800-555-ETHICS.

## Conflicts of Interest
Employees must disclose any personal financial interests that could conflict with
company interests. Outside employment requires written approval from your manager.

## Confidentiality
Proprietary information must not be shared outside the company. NDAs are required
for all employees and contractors. Violations may result in termination and legal action.
"""

    # === Engineering (6 docs) ===
    docs["engineering/architecture-overview.md"] = """# System Architecture Overview

## High-Level Design
The platform follows a microservices architecture deployed on Kubernetes (EKS).
Services communicate via gRPC for internal calls and REST for external APIs.

## Core Services
- API Gateway (Kong): rate limiting, auth, routing
- User Service: authentication, profiles, permissions
- Order Service: order lifecycle management
- Payment Service: Stripe integration, invoicing
- Notification Service: email, push, SMS via SNS

## Data Layer
PostgreSQL for transactional data. Redis for caching and sessions.
Elasticsearch for full-text search. S3 for file storage.

## Infrastructure
Terraform for IaC. ArgoCD for GitOps deployments. Datadog for monitoring.
All services run in us-east-1 with disaster recovery in us-west-2.
"""

    docs["engineering/api-standards.md"] = """# API Standards

## REST Conventions
All APIs follow RESTful conventions. Use plural nouns for resources (/users, /orders).
Return appropriate HTTP status codes. Paginate list endpoints with cursor-based pagination.

## Authentication
All APIs require Bearer token authentication via JWT. Tokens expire after 1 hour.
Refresh tokens are valid for 30 days. API keys are used for service-to-service calls.

## Versioning
APIs are versioned via URL path (/v1/, /v2/). Breaking changes require a new version.
Old versions are supported for 12 months after deprecation notice.

## Error Format
All errors return JSON: {"error": {"code": "NOT_FOUND", "message": "...", "details": []}}.
Use standard error codes: VALIDATION_ERROR, NOT_FOUND, UNAUTHORIZED, RATE_LIMITED.
"""

    docs["engineering/deployment-guide.md"] = """# Deployment Guide

## CI/CD Pipeline
GitHub Actions runs on every PR: lint, test, build Docker image, security scan.
Merges to main auto-deploy to staging. Production deploys require manual approval
in ArgoCD.

## Environments
- Development: dev.acme.internal (auto-deploy from feature branches)
- Staging: staging.acme.internal (auto-deploy from main)
- Production: api.acme.com (manual approval required)

## Rollback
ArgoCD supports instant rollback to any previous deployment. If a production deploy
causes issues, use `argocd app rollback <app> <revision>`. All rollbacks are logged.

## Database Migrations
Migrations run automatically during deployment via Flyway. Backward-compatible migrations
only. Destructive changes require a two-phase migration plan reviewed by the DBA team.
"""

    docs["engineering/security-practices.md"] = """# Security Practices

## Access Control
All systems use role-based access control (RBAC). Production access requires VPN + MFA.
SSH access to production servers is disabled; use AWS SSM Session Manager instead.

## Secrets Management
All secrets stored in AWS Secrets Manager. Never commit secrets to git. Environment
variables are injected at runtime via Kubernetes secrets. Rotate credentials quarterly.

## Vulnerability Management
Dependabot scans for dependency vulnerabilities weekly. Critical CVEs must be patched
within 48 hours. High severity within 1 week. Snyk scans Docker images on every build.

## Incident Response
Security incidents follow the SIRT process: detect, triage, contain, eradicate, recover.
All incidents are documented in the incident log. Post-mortems required for P1/P2 incidents.
"""

    docs["engineering/database-guide.md"] = """# Database Guide

## PostgreSQL
Primary database for all transactional data. Running on RDS with Multi-AZ deployment.
Connection pooling via PgBouncer. Read replicas for reporting queries.

## Schema Conventions
Tables use snake_case naming. All tables have id (UUID), created_at, updated_at columns.
Foreign keys are always indexed. Use JSONB sparingly — prefer normalized schemas.

## Performance
Queries exceeding 100ms are flagged in Datadog. N+1 queries are prohibited. Use EXPLAIN
ANALYZE for query optimization. Index usage is reviewed monthly.

## Backups
Automated daily snapshots with 30-day retention. Point-in-time recovery available within
the retention window. Backup restoration tested quarterly.
"""

    docs["engineering/monitoring-runbook.md"] = """# Monitoring Runbook

## Dashboards
- System Overview: grafana.acme.internal/d/system-overview
- API Latency: grafana.acme.internal/d/api-latency (on-call watches this)
- Error Rates: grafana.acme.internal/d/error-rates
- Database Health: grafana.acme.internal/d/db-health

## Alerts
P1 (page immediately): API error rate > 5%, latency p99 > 2s, database connection failures
P2 (respond within 1h): Disk usage > 80%, memory > 90%, certificate expiry < 14 days
P3 (next business day): Dependency vulnerabilities, non-critical service degradation

## On-Call
Rotation: weekly, Mon 9 AM to Mon 9 AM. PagerDuty for P1/P2 alerts.
Handoff meeting every Monday at 9:30 AM. On-call engineer has production access.

## Common Issues
1. High API latency → Check database slow query log, verify connection pool health
2. 5xx errors spike → Check service logs in Datadog, look for OOM kills in K8s
3. Queue backlog → Check consumer lag in Kafka dashboard, verify consumer health
"""

    # === Projects (6 docs) ===
    docs["projects/atlas-data-platform.md"] = """# Project Atlas — Data Platform

## Overview
Project Atlas is the next-generation data platform initiative to consolidate all data
pipelines into a unified lakehouse architecture using Apache Iceberg and Spark.

## Goals
1. Replace 12 legacy ETL pipelines with a unified ingestion framework
2. Reduce data processing costs by 40%
3. Enable self-service analytics for business teams
4. Achieve SOC 2 compliance for data handling

## Architecture
Ingestion: Kafka + Flink for real-time, Airflow for batch
Storage: S3 + Apache Iceberg for the lakehouse
Compute: Spark for transforms, Trino for interactive queries
Governance: Unity Catalog for metadata and access control

## Team
Lead: Sarah Chen (Principal Engineer), 4 backend, 3 data eng, 2 DevOps, PM: James Rodriguez

## Timeline
Architecture Review: Feb 2026 (Complete)
Ingestion MVP: Apr 2026 (In Progress)
Storage Layer: Jun 2026 (Planned)
Self-Service Analytics: Sep 2026 (Planned)
"""

    docs["projects/phoenix-mobile-app.md"] = """# Project Phoenix — Mobile App Redesign

## Overview
Complete redesign of the customer-facing mobile app. Moving from React Native to
native Swift (iOS) and Kotlin (Android) for better performance and UX.

## Goals
1. Reduce app startup time from 4.2s to under 1.5s
2. Increase daily active users by 30%
3. Implement offline-first architecture
4. Add biometric authentication

## Tech Stack
iOS: Swift + SwiftUI + Combine
Android: Kotlin + Jetpack Compose + Coroutines
Backend: existing API with new GraphQL layer
CI/CD: Fastlane + GitHub Actions

## Team
Lead: Marcus Johnson (Sr. Mobile Engineer), 3 iOS, 3 Android, 1 backend, 1 QA

## Timeline
Design Complete: Mar 2026 (Complete)
iOS Beta: May 2026 (In Progress)
Android Beta: Jun 2026 (Planned)
Public Launch: Aug 2026 (Planned)
"""

    docs["projects/sentinel-security.md"] = """# Project Sentinel — Security Platform

## Overview
Building an internal security operations platform to centralize threat detection,
vulnerability management, and compliance monitoring.

## Goals
1. Centralize security alerts from 8 different tools into one dashboard
2. Automate 60% of routine security triage
3. Reduce mean time to detect (MTTD) from 4 hours to 30 minutes
4. Achieve ISO 27001 certification

## Components
SIEM: Elasticsearch + custom detection rules
SOAR: Automated playbooks for common incidents
Vulnerability Scanner: Nessus + custom integrations
Compliance: Policy-as-code with Open Policy Agent

## Team
Lead: Aisha Patel (Security Engineering Manager), 2 security eng, 2 backend, 1 DevOps
"""

    docs["projects/horizon-ai-assistant.md"] = """# Project Horizon — AI Assistant

## Overview
Internal AI assistant for employees, powered by LLMs with access to company knowledge.
Uses RAG for grounding responses in company data.

## Goals
1. Answer employee questions about policies, processes, and projects
2. Draft emails, summarize meetings, generate reports
3. Integration with Slack, email, and internal tools
4. Governance layer for safe AI usage

## Architecture
LLM: Claude via Anthropic API
RAG: Vector store (pgvector) + document ingestion pipeline
Guardrails: theaios-guardrails for input/output filtering
Context: theaios-context-router for data delivery
Trust: theaios-trustgate for reliability certification

## Team
Lead: David Kim (ML Engineer), 2 ML eng, 1 backend, 1 product designer
"""

    docs["projects/meridian-crm.md"] = """# Project Meridian — CRM Migration

## Overview
Migrating from Salesforce to a custom CRM built on our platform. Driven by cost
reduction ($400K/year in Salesforce licenses) and deeper integration needs.

## Goals
1. Replicate core Salesforce functionality (contacts, deals, pipeline)
2. Deep integration with our billing and support systems
3. Custom analytics dashboards
4. Reduce CRM costs by 70%

## Data Migration
Phase 1: Export all Salesforce data (contacts, accounts, opportunities, activities)
Phase 2: Transform to new schema (6-week effort)
Phase 3: Parallel run with both systems for 30 days
Phase 4: Cutover and decommission Salesforce

## Team
Lead: Lisa Wang (Sr. Backend Engineer), 3 backend, 1 frontend, 1 data eng
"""

    docs["projects/quarterly-roadmap.md"] = """# Q2 2026 Roadmap

## Engineering Priorities
1. Project Atlas: Complete ingestion MVP and begin storage layer
2. Project Phoenix: Ship iOS beta to TestFlight
3. Project Sentinel: Launch centralized SIEM dashboard
4. Infrastructure: Migrate remaining services to ARM-based instances (30% cost reduction)

## Product Priorities
1. Self-service analytics MVP (Atlas dependency)
2. Mobile app beta program (Phoenix dependency)
3. Customer portal v2 with AI-powered search
4. API rate limiting improvements for enterprise tier

## Hiring
- 2 Senior Backend Engineers (Atlas team)
- 1 iOS Engineer (Phoenix team)
- 1 Security Engineer (Sentinel team)
- 1 DevOps Engineer (Infrastructure)

## Key Dates
- Apr 1: Atlas Ingestion MVP demo
- May 1: Phoenix iOS beta release
- Jun 1: Sentinel SIEM launch
- Jun 30: Q2 retrospective and Q3 planning
"""

    # === Finance (6 docs) ===
    docs["finance/q3-2025-results.md"] = """# Q3 2025 Financial Results

## Revenue
Total revenue: $12.4M (up 18% YoY)
Recurring revenue (ARR): $10.2M
Professional services: $2.2M

## Expenses
Total operating expenses: $9.8M
- Engineering: $4.2M (43%)
- Sales & Marketing: $2.8M (29%)
- G&A: $1.5M (15%)
- Infrastructure: $1.3M (13%)

## Profitability
Gross margin: 72%
Operating income: $2.6M
Net income: $2.1M
Cash on hand: $15.3M

## Key Metrics
Customers: 847 (up from 712 in Q3 2024)
Net Revenue Retention: 115%
Customer Acquisition Cost: $8,200
Lifetime Value: $42,000
LTV/CAC ratio: 5.1x
"""

    docs["finance/budget-2026.md"] = """# 2026 Annual Budget

## Revenue Target
Total revenue target: $58M (32% growth)
- Q1: $13.2M, Q2: $14.1M, Q3: $15.0M, Q4: $15.7M

## Headcount Budget
Current headcount: 142
Planned end-of-year: 178
New hires: 36 across Engineering (18), Sales (8), Product (4), G&A (6)

## Capital Expenditure
Cloud infrastructure: $6.2M
Office expansion: $1.8M
Equipment (laptops, monitors): $540K

## Department Budgets
Engineering: $22M (38%)
Sales & Marketing: $15M (26%)
Product: $6M (10%)
G&A: $8M (14%)
Infrastructure: $7M (12%)
"""

    docs["finance/vendor-contracts.md"] = """# Active Vendor Contracts

## Cloud & Infrastructure
- AWS: $480K/month, 3-year committed spend, expires Dec 2027
- Datadog: $15K/month, annual contract, renews Mar 2027
- PagerDuty: $2K/month, annual contract, renews Jun 2026

## SaaS & Tools
- Slack: $18/user/month, 142 seats = $30.7K/year
- GitHub Enterprise: $21/user/month, 95 seats = $23.9K/year
- Figma: $15/user/month, 12 seats = $2.2K/year
- Notion: $10/user/month, 142 seats = $17K/year

## Professional Services
- Outside counsel (Wilson & Associates): $450/hour, retainer $25K/month
- Audit firm (Deloitte): Annual audit $180K
- Recruiting (Hired, LinkedIn): ~$120K/year
"""

    docs["finance/procurement-process.md"] = """# Procurement Process

## Approval Thresholds
- Under $5K: Manager approval
- $5K-$25K: Director approval + Finance review
- $25K-$100K: VP approval + Legal review + Finance review
- Over $100K: CEO approval + Board notification

## Vendor Evaluation
All new vendors must complete: security questionnaire, SOC 2 report review,
data processing agreement (DPA), and reference check. Timeline: 2-4 weeks.

## Purchase Orders
All purchases over $1K require a PO. POs are generated in NetSuite.
Payment terms: Net 30 for standard vendors, Net 60 for enterprise contracts.

## Contract Review
Legal must review all contracts over $25K or with non-standard terms.
Auto-renewal clauses must be flagged 90 days before renewal date.
"""

    docs["finance/tax-compliance.md"] = """# Tax Compliance Overview

## Federal Taxes
Corporate income tax filings due April 15 (extension available to October 15).
Estimated quarterly tax payments due April 15, June 15, September 15, January 15.

## State Taxes
Currently registered in: Delaware (incorporation), California, New York, Texas, Washington.
Sales tax nexus established in 12 states. Sales tax collected and remitted monthly.

## International
Transfer pricing documentation maintained for all intercompany transactions.
Permanent establishment analysis conducted annually for each jurisdiction.

## R&D Tax Credits
Qualifying R&D activities documented quarterly. Annual R&D credit claim of approximately
$1.2M. Documentation maintained for 7 years per IRS requirements.
"""

    docs["finance/investor-relations.md"] = """# Investor Relations

## Current Investors
Series A: Sequoia Capital ($15M, 2023)
Series B: Andreessen Horowitz ($40M, 2024)
Total raised: $58M

## Board Members
- CEO: Alex Thompson
- Sequoia representative: Jamie Lee
- a16z representative: Chris Morgan
- Independent: Dr. Rachel Foster (former CTO, Stripe)

## Reporting
Monthly financial package to board members by the 10th of each month.
Quarterly board meeting (last Thursday of quarter-end month).
Annual financial audit by Deloitte, completed by March 31.

## Cap Table
Founders: 35%, Series A: 18%, Series B: 22%, Employee pool: 20%, Unallocated: 5%.
"""

    # === Sales / Customer (6 docs) ===
    docs["sales/sales-playbook.md"] = """# Sales Playbook

## Ideal Customer Profile
Mid-market companies (200-2000 employees) in technology, financial services, or healthcare.
Annual revenue $50M-$500M. Currently using 3+ disconnected SaaS tools for their workflow.

## Sales Process
1. Discovery call (30 min): understand pain points, current stack, budget
2. Demo (45 min): tailored to their use case
3. Technical evaluation (1-2 weeks): proof of concept with their data
4. Proposal and negotiation (1-2 weeks)
5. Legal review and contract (1-2 weeks)
Average sales cycle: 45 days

## Pricing
Starter: $500/month (up to 50 users)
Professional: $2,000/month (up to 200 users)
Enterprise: Custom pricing (200+ users, SSO, dedicated support)

## Objection Handling
"Too expensive" → ROI calculator shows 3x return in first year
"We already have tools" → migration assistance included, 90-day parallel run
"Security concerns" → SOC 2 Type II certified, encryption at rest and in transit
"""

    docs["sales/customer-case-studies.md"] = """# Customer Case Studies

## TechCorp (Technology, 500 employees)
Challenge: 6 disconnected tools, data silos, manual reporting
Solution: Unified platform replacing Salesforce + Jira + Confluence
Results: 40% reduction in tool costs, 25% faster project delivery, 90% user adoption

## HealthFirst (Healthcare, 1200 employees)
Challenge: HIPAA compliance across multiple systems, audit failures
Solution: Centralized platform with built-in compliance controls
Results: Zero audit findings, $200K annual savings, 60% faster compliance reporting

## FinServe Capital (Financial Services, 800 employees)
Challenge: Slow client onboarding (avg 3 weeks), manual KYC process
Solution: Automated onboarding workflow with integrated KYC checks
Results: Onboarding reduced to 3 days, 50% increase in client capacity
"""

    docs["sales/competitor-analysis.md"] = """# Competitor Analysis

## Salesforce
Strengths: Market leader, extensive ecosystem, AppExchange
Weaknesses: Expensive ($150-300/user/month), complex, slow to customize
Our advantage: 70% lower cost, faster implementation, built-in AI

## HubSpot
Strengths: Easy to use, good marketing automation, free tier
Weaknesses: Limited enterprise features, weak reporting, no custom objects
Our advantage: Enterprise-grade features, custom workflows, better analytics

## ServiceNow
Strengths: IT service management leader, workflow automation
Weaknesses: Very expensive, long implementation (6-12 months), steep learning curve
Our advantage: 10x faster deployment, intuitive UI, lower TCO

## Freshworks
Strengths: Affordable, easy setup, good for SMB
Weaknesses: Limited scalability, basic integrations, weak API
Our advantage: Scales to enterprise, robust API, deep integrations
"""

    docs["sales/pipeline-report.md"] = """# Sales Pipeline Report — March 2026

## Summary
Total pipeline value: $4.2M
Weighted pipeline: $1.8M
Average deal size: $48K ARR
Win rate (trailing 90 days): 32%

## Stage Breakdown
- Qualification: 18 deals, $1.1M
- Demo Scheduled: 12 deals, $890K
- Technical Evaluation: 8 deals, $720K
- Proposal Sent: 6 deals, $580K
- Negotiation: 4 deals, $420K
- Verbal Commit: 3 deals, $480K

## Top Deals
1. GlobalTech Inc: $180K ARR (Negotiation, close expected April)
2. MedLife Systems: $150K ARR (Technical Eval, strong champion)
3. Pacific Finance: $120K ARR (Proposal Sent, competing with Salesforce)
"""

    docs["sales/pricing-calculator.md"] = """# Pricing Calculator Guide

## Base Pricing
Starter ($500/mo): Up to 50 users, 5 integrations, email support
Professional ($2,000/mo): Up to 200 users, unlimited integrations, priority support
Enterprise (custom): Unlimited users, SSO, dedicated CSM, SLA, custom training

## Add-Ons
Advanced Analytics: +$300/month
API Access (above 10K calls/month): +$200/month
Custom Integrations: $5,000 one-time setup per integration
Data Migration: $10,000-$50,000 depending on complexity

## Discounts
Annual payment: 15% discount
Multi-year (2+): 20% discount
Non-profit: 30% discount
Startup (<50 employees, <$10M revenue): 40% discount

## ROI Model
Average customer saves 25 hours/employee/month
At $50/hour blended rate = $1,250/employee/month in recovered capacity
Break-even typically within 2-3 months for Professional tier
"""

    docs["sales/partner-program.md"] = """# Partner Program

## Partner Tiers
Silver: Completed certification, 1+ customer referral
Gold: 5+ customer referrals, dedicated partner manager
Platinum: 15+ customer referrals, co-marketing, revenue share

## Revenue Share
Silver: 10% of first-year revenue
Gold: 15% of first-year revenue + 5% recurring
Platinum: 20% of first-year revenue + 10% recurring

## Certification
Partners must complete the 3-day certification program covering:
- Platform overview and architecture
- Implementation best practices
- Sales methodology and objection handling
- Support and troubleshooting

## Co-Marketing
Gold+ partners get: joint webinars, case study co-authoring,
logo placement on partner page, joint conference booth.
"""

    # Write all documents
    for path, content in docs.items():
        full_path = DOCS_DIR / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content.strip() + "\n", encoding="utf-8")

    return docs


def create_queries(docs: dict[str, str]) -> None:
    """Create 60 labeled queries with ground-truth relevance."""

    queries = [
        # --- HR / Policy queries (12) ---
        {
            "id": "q01", "text": "What is the remote work policy?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/remote-work-policy.md"],
            "irrelevant_docs": ["finance/q3-2025-results.md", "engineering/api-standards.md"],
        },
        {
            "id": "q02", "text": "How do I submit expense reports?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/expense-policy.md"],
            "irrelevant_docs": ["sales/pricing-calculator.md", "projects/atlas-data-platform.md"],
        },
        {
            "id": "q03", "text": "How many PTO days do I get per year?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/pto-policy.md"],
            "irrelevant_docs": ["finance/budget-2026.md", "engineering/deployment-guide.md"],
        },
        {
            "id": "q04", "text": "What are the salary bands for senior engineers?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/compensation-structure.md"],
            "irrelevant_docs": ["sales/pipeline-report.md", "projects/phoenix-mobile-app.md"],
        },
        {
            "id": "q05", "text": "What should I do on my first week at the company?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/onboarding-guide.md"],
            "irrelevant_docs": ["engineering/monitoring-runbook.md", "finance/tax-compliance.md"],
        },
        {
            "id": "q06", "text": "Where do I report harassment or discrimination?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/code-of-conduct.md"],
            "irrelevant_docs": ["sales/competitor-analysis.md", "projects/sentinel-security.md"],
        },
        {
            "id": "q07", "text": "Can I work from home as a part-time contractor?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/remote-work-policy.md"],
            "irrelevant_docs": ["finance/vendor-contracts.md", "engineering/database-guide.md"],
        },
        {
            "id": "q08", "text": "What is the maximum hotel rate for business travel in NYC?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/expense-policy.md"],
            "irrelevant_docs": ["projects/meridian-crm.md", "sales/sales-playbook.md"],
        },
        {
            "id": "q09", "text": "When does health insurance coverage begin for new hires?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/onboarding-guide.md"],
            "irrelevant_docs": ["engineering/security-practices.md", "finance/investor-relations.md"],
        },
        {
            "id": "q10", "text": "How does the stock option vesting schedule work?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/compensation-structure.md"],
            "irrelevant_docs": ["projects/quarterly-roadmap.md", "sales/partner-program.md"],
        },
        {
            "id": "q11", "text": "What are the core working hours for remote employees?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/remote-work-policy.md"],
            "irrelevant_docs": ["engineering/architecture-overview.md", "finance/procurement-process.md"],
        },
        {
            "id": "q12", "text": "Can I carry over unused vacation days to next year?",
            "domain": "hr", "expected_route": "hr-policies",
            "relevant_docs": ["hr/pto-policy.md"],
            "irrelevant_docs": ["sales/customer-case-studies.md", "projects/horizon-ai-assistant.md"],
        },

        # --- Engineering queries (12) ---
        {
            "id": "q13", "text": "What is our system architecture?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/architecture-overview.md"],
            "irrelevant_docs": ["hr/expense-policy.md", "finance/budget-2026.md"],
        },
        {
            "id": "q14", "text": "How do I deploy to production?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/deployment-guide.md"],
            "irrelevant_docs": ["hr/pto-policy.md", "sales/pipeline-report.md"],
        },
        {
            "id": "q15", "text": "What are our API authentication standards?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/api-standards.md"],
            "irrelevant_docs": ["finance/tax-compliance.md", "projects/phoenix-mobile-app.md"],
        },
        {
            "id": "q16", "text": "How do we handle secrets and credentials?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/security-practices.md"],
            "irrelevant_docs": ["hr/compensation-structure.md", "sales/competitor-analysis.md"],
        },
        {
            "id": "q17", "text": "What database do we use and what are the conventions?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/database-guide.md"],
            "irrelevant_docs": ["finance/vendor-contracts.md", "hr/onboarding-guide.md"],
        },
        {
            "id": "q18", "text": "What should I do when API latency is high?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/monitoring-runbook.md"],
            "irrelevant_docs": ["sales/pricing-calculator.md", "projects/meridian-crm.md"],
        },
        {
            "id": "q19", "text": "How do I rollback a bad production deployment?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/deployment-guide.md"],
            "irrelevant_docs": ["hr/code-of-conduct.md", "finance/q3-2025-results.md"],
        },
        {
            "id": "q20", "text": "What are the P1 alert thresholds?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/monitoring-runbook.md"],
            "irrelevant_docs": ["projects/atlas-data-platform.md", "sales/partner-program.md"],
        },
        {
            "id": "q21", "text": "How do we handle database migrations?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/deployment-guide.md", "engineering/database-guide.md"],
            "irrelevant_docs": ["hr/remote-work-policy.md", "finance/investor-relations.md"],
        },
        {
            "id": "q22", "text": "What is our incident response process for security issues?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/security-practices.md"],
            "irrelevant_docs": ["sales/sales-playbook.md", "projects/quarterly-roadmap.md"],
        },
        {
            "id": "q23", "text": "What is the on-call rotation schedule?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/monitoring-runbook.md"],
            "irrelevant_docs": ["hr/pto-policy.md", "finance/procurement-process.md"],
        },
        {
            "id": "q24", "text": "How do we version our REST APIs?",
            "domain": "engineering", "expected_route": "engineering",
            "relevant_docs": ["engineering/api-standards.md"],
            "irrelevant_docs": ["projects/horizon-ai-assistant.md", "sales/customer-case-studies.md"],
        },

        # --- Project queries (12) ---
        {
            "id": "q25", "text": "What is the status of Project Atlas?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/atlas-data-platform.md"],
            "irrelevant_docs": ["hr/expense-policy.md", "finance/budget-2026.md"],
        },
        {
            "id": "q26", "text": "Who is leading the mobile app redesign?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/phoenix-mobile-app.md"],
            "irrelevant_docs": ["engineering/api-standards.md", "sales/pipeline-report.md"],
        },
        {
            "id": "q27", "text": "What are the Q2 engineering priorities?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/quarterly-roadmap.md"],
            "irrelevant_docs": ["hr/pto-policy.md", "finance/tax-compliance.md"],
        },
        {
            "id": "q28", "text": "What is Project Sentinel about?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/sentinel-security.md"],
            "irrelevant_docs": ["sales/competitor-analysis.md", "hr/compensation-structure.md"],
        },
        {
            "id": "q29", "text": "What AI tools does the Horizon project use?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/horizon-ai-assistant.md"],
            "irrelevant_docs": ["engineering/database-guide.md", "finance/vendor-contracts.md"],
        },
        {
            "id": "q30", "text": "Why are we migrating away from Salesforce?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/meridian-crm.md"],
            "irrelevant_docs": ["hr/onboarding-guide.md", "engineering/deployment-guide.md"],
        },
        {
            "id": "q31", "text": "When is the iOS beta expected to ship?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/phoenix-mobile-app.md", "projects/quarterly-roadmap.md"],
            "irrelevant_docs": ["finance/q3-2025-results.md", "sales/sales-playbook.md"],
        },
        {
            "id": "q32", "text": "What tech stack is Atlas built on?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/atlas-data-platform.md"],
            "irrelevant_docs": ["hr/code-of-conduct.md", "finance/procurement-process.md"],
        },
        {
            "id": "q33", "text": "How many engineers are we hiring this quarter?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/quarterly-roadmap.md"],
            "irrelevant_docs": ["sales/partner-program.md", "engineering/security-practices.md"],
        },
        {
            "id": "q34", "text": "What is the goal for reducing data processing costs?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/atlas-data-platform.md"],
            "irrelevant_docs": ["hr/remote-work-policy.md", "sales/pricing-calculator.md"],
        },
        {
            "id": "q35", "text": "What compliance certifications are we pursuing?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/atlas-data-platform.md", "projects/sentinel-security.md"],
            "irrelevant_docs": ["finance/investor-relations.md", "hr/expense-policy.md"],
        },
        {
            "id": "q36", "text": "What is the CRM data migration plan?",
            "domain": "projects", "expected_route": "projects",
            "relevant_docs": ["projects/meridian-crm.md"],
            "irrelevant_docs": ["engineering/monitoring-runbook.md", "sales/customer-case-studies.md"],
        },

        # --- Finance queries (12) ---
        {
            "id": "q37", "text": "What was our Q3 2025 revenue?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/q3-2025-results.md"],
            "irrelevant_docs": ["hr/pto-policy.md", "engineering/architecture-overview.md"],
        },
        {
            "id": "q38", "text": "What is the 2026 revenue target?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/budget-2026.md"],
            "irrelevant_docs": ["sales/sales-playbook.md", "projects/phoenix-mobile-app.md"],
        },
        {
            "id": "q39", "text": "How much do we spend on AWS per month?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/vendor-contracts.md"],
            "irrelevant_docs": ["hr/remote-work-policy.md", "engineering/deployment-guide.md"],
        },
        {
            "id": "q40", "text": "What is the procurement approval process for large purchases?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/procurement-process.md"],
            "irrelevant_docs": ["projects/atlas-data-platform.md", "sales/competitor-analysis.md"],
        },
        {
            "id": "q41", "text": "When are quarterly tax payments due?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/tax-compliance.md"],
            "irrelevant_docs": ["hr/compensation-structure.md", "engineering/api-standards.md"],
        },
        {
            "id": "q42", "text": "Who are our investors and how much have we raised?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/investor-relations.md"],
            "irrelevant_docs": ["projects/quarterly-roadmap.md", "sales/partner-program.md"],
        },
        {
            "id": "q43", "text": "What is our customer acquisition cost?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/q3-2025-results.md"],
            "irrelevant_docs": ["hr/onboarding-guide.md", "engineering/database-guide.md"],
        },
        {
            "id": "q44", "text": "What is our headcount plan for 2026?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/budget-2026.md", "projects/quarterly-roadmap.md"],
            "irrelevant_docs": ["sales/pipeline-report.md", "hr/code-of-conduct.md"],
        },
        {
            "id": "q45", "text": "How much do we pay for Slack and GitHub?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/vendor-contracts.md"],
            "irrelevant_docs": ["engineering/security-practices.md", "projects/horizon-ai-assistant.md"],
        },
        {
            "id": "q46", "text": "What is the R&D tax credit amount?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/tax-compliance.md"],
            "irrelevant_docs": ["sales/customer-case-studies.md", "hr/expense-policy.md"],
        },
        {
            "id": "q47", "text": "Who is on the board of directors?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/investor-relations.md"],
            "irrelevant_docs": ["projects/meridian-crm.md", "engineering/monitoring-runbook.md"],
        },
        {
            "id": "q48", "text": "What is the engineering department budget for 2026?",
            "domain": "finance", "expected_route": "finance",
            "relevant_docs": ["finance/budget-2026.md"],
            "irrelevant_docs": ["hr/pto-policy.md", "sales/pricing-calculator.md"],
        },

        # --- Sales queries (12) ---
        {
            "id": "q49", "text": "What is our ideal customer profile?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/sales-playbook.md"],
            "irrelevant_docs": ["hr/remote-work-policy.md", "finance/tax-compliance.md"],
        },
        {
            "id": "q50", "text": "How do we compare to Salesforce?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/competitor-analysis.md"],
            "irrelevant_docs": ["engineering/architecture-overview.md", "projects/atlas-data-platform.md"],
        },
        {
            "id": "q51", "text": "What are our pricing tiers?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/pricing-calculator.md", "sales/sales-playbook.md"],
            "irrelevant_docs": ["hr/compensation-structure.md", "finance/budget-2026.md"],
        },
        {
            "id": "q52", "text": "What is the current pipeline value?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/pipeline-report.md"],
            "irrelevant_docs": ["engineering/deployment-guide.md", "projects/sentinel-security.md"],
        },
        {
            "id": "q53", "text": "Tell me about customer success stories",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/customer-case-studies.md"],
            "irrelevant_docs": ["hr/onboarding-guide.md", "finance/procurement-process.md"],
        },
        {
            "id": "q54", "text": "How does the partner revenue share work?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/partner-program.md"],
            "irrelevant_docs": ["engineering/api-standards.md", "projects/quarterly-roadmap.md"],
        },
        {
            "id": "q55", "text": "What is the average sales cycle length?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/sales-playbook.md"],
            "irrelevant_docs": ["finance/investor-relations.md", "hr/pto-policy.md"],
        },
        {
            "id": "q56", "text": "How do I handle price objections from prospects?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/sales-playbook.md", "sales/pricing-calculator.md"],
            "irrelevant_docs": ["engineering/database-guide.md", "projects/phoenix-mobile-app.md"],
        },
        {
            "id": "q57", "text": "What is the biggest deal in the pipeline right now?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/pipeline-report.md"],
            "irrelevant_docs": ["hr/code-of-conduct.md", "finance/q3-2025-results.md"],
        },
        {
            "id": "q58", "text": "What discounts can we offer for annual payment?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/pricing-calculator.md"],
            "irrelevant_docs": ["engineering/security-practices.md", "projects/horizon-ai-assistant.md"],
        },
        {
            "id": "q59", "text": "Who are our main competitors and how do we differentiate?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/competitor-analysis.md"],
            "irrelevant_docs": ["finance/vendor-contracts.md", "hr/expense-policy.md"],
        },
        {
            "id": "q60", "text": "What results did HealthFirst achieve with our platform?",
            "domain": "sales", "expected_route": "sales",
            "relevant_docs": ["sales/customer-case-studies.md"],
            "irrelevant_docs": ["projects/meridian-crm.md", "engineering/monitoring-runbook.md"],
        },
    ]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "queries.json").write_text(
        json.dumps(queries, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Created {len(queries)} queries in {DATA_DIR / 'queries.json'}")


def main() -> None:
    print("Creating benchmark dataset...")
    print()
    docs = create_documents()
    print(f"Created {len(docs)} documents in {DOCS_DIR}/")
    for domain in sorted({p.split("/")[0] for p in docs}):
        count = sum(1 for p in docs if p.startswith(domain + "/"))
        print(f"  {domain}: {count} docs")
    print()
    create_queries(docs)
    print()
    print("Done.")


if __name__ == "__main__":
    main()
