# Project Atlas

## Overview

Project Atlas is the company's next-generation data platform initiative. The goal is to
consolidate all data pipelines into a unified lakehouse architecture using Apache Iceberg
and Spark. The project is expected to run from Q1 2026 through Q3 2026 with a budget of
$2.4M.

## Architecture

The platform is built on three layers: ingestion (Kafka + Flink), storage (S3 + Iceberg),
and compute (Spark + Trino). A metadata catalog powered by Unity Catalog provides governance
and lineage tracking. All infrastructure is deployed on AWS using Terraform.

## Team

- **Lead**: Sarah Chen (Principal Engineer)
- **Backend**: 4 engineers
- **Data Engineering**: 3 engineers
- **DevOps**: 2 engineers
- **PM**: James Rodriguez

## Milestones

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Architecture Review | 2026-02-15 | Complete |
| Ingestion MVP | 2026-04-01 | In Progress |
| Storage Layer | 2026-05-15 | Planned |
| Compute Layer | 2026-07-01 | Planned |
| Full Migration | 2026-09-30 | Planned |
