"""Language registry + prompt/config data for the AI code-eval engine.

Moved verbatim from services/ai_engine.py (decomposition backlog) — pure
configuration, no logic. ai_engine star-imports this for compatibility.
"""
from __future__ import annotations
"""
AI Code Evaluation Engine — StudyBuddy Enterprise v4
Pure AI-based evaluation. No sandbox. No subprocess. No Docker dependency.
Supports 50+ enterprise languages via Gemini 2.0 Flash with LangGraph orchestration.
Mentor grading layer is separate — AI gives initial score, mentor can override.
"""


import datetime
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, TypedDict

from config import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    HarmBlockThreshold,
    HarmCategory,
)
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ── Enterprise Language Registry ─────────────────────────────────────────────
# This is the master list. It drives Monaco editor intellisense on the frontend.
# Each entry: id (API key), name (display), monaco_language (Monaco identifier),
#             category (for grouping in UI), ai_context (injected into eval prompt)

ENTERPRISE_LANGUAGES: List[Dict] = [
    # ── Shell & Scripting ──────────────────────────────────────────────────
    {
        "id": "bash",
        "name": "Bash / Shell",
        "monaco_language": "shell",
        "category": "Scripting",
        "ai_context": "Unix shell scripting, POSIX compliance, pipe operators, process substitution, trap handlers",
    },
    {
        "id": "powershell",
        "name": "PowerShell",
        "monaco_language": "powershell",
        "category": "Scripting",
        "ai_context": "Windows PowerShell 7+, cmdlets, modules, pipeline, remoting, DSC",
    },
    {
        "id": "zsh",
        "name": "Zsh",
        "monaco_language": "shell",
        "category": "Scripting",
        "ai_context": "Zsh scripting, Oh-My-Zsh, autocompletion, globbing, parameter expansion",
    },
    # ── Systems & General Purpose ──────────────────────────────────────────
    {
        "id": "python",
        "name": "Python 3",
        "monaco_language": "python",
        "category": "General",
        "ai_context": "Python 3.11+, PEP standards, type hints, async/await, dataclasses, context managers",
    },
    {
        "id": "javascript",
        "name": "JavaScript (ES2024)",
        "monaco_language": "javascript",
        "category": "General",
        "ai_context": "Modern JavaScript ES2024, promises, async/await, destructuring, modules, WeakRef",
    },
    {
        "id": "typescript",
        "name": "TypeScript",
        "monaco_language": "typescript",
        "category": "General",
        "ai_context": "TypeScript 5+, generics, decorators, utility types, strict mode, template literal types",
    },
    {
        "id": "go",
        "name": "Go",
        "monaco_language": "go",
        "category": "General",
        "ai_context": "Go 1.22+, goroutines, channels, interfaces, error wrapping, generics",
    },
    {
        "id": "rust",
        "name": "Rust",
        "monaco_language": "rust",
        "category": "General",
        "ai_context": "Rust ownership, borrowing, lifetimes, traits, async Tokio, error handling with thiserror",
    },
    {
        "id": "java",
        "name": "Java 21",
        "monaco_language": "java",
        "category": "General",
        "ai_context": "Java 21 LTS, records, sealed classes, pattern matching, virtual threads, Stream API",
    },
    {
        "id": "kotlin",
        "name": "Kotlin",
        "monaco_language": "kotlin",
        "category": "General",
        "ai_context": "Kotlin coroutines, data classes, extension functions, sealed classes, null safety",
    },
    {
        "id": "scala",
        "name": "Scala 3",
        "monaco_language": "scala",
        "category": "General",
        "ai_context": "Scala 3, functional programming, Akka, Spark, implicit parameters, type classes",
    },
    {
        "id": "csharp",
        "name": "C#",
        "monaco_language": "csharp",
        "category": "General",
        "ai_context": "C# 12, .NET 8, LINQ, async/await, records, pattern matching, minimal APIs",
    },
    # ── Web Frontend ───────────────────────────────────────────────────────
    {
        "id": "react",
        "name": "React (JSX/TSX)",
        "monaco_language": "typescript",
        "category": "Frontend",
        "ai_context": "React 18+, hooks, Suspense, concurrent features, RSC, useTransition, Context API",
    },
    {
        "id": "nextjs",
        "name": "Next.js 14",
        "monaco_language": "typescript",
        "category": "Frontend",
        "ai_context": "Next.js 14 App Router, Server Components, Server Actions, streaming, Metadata API, middleware",
    },
    {
        "id": "vue",
        "name": "Vue 3",
        "monaco_language": "typescript",
        "category": "Frontend",
        "ai_context": "Vue 3 Composition API, script setup, Pinia, reactivity, defineProps, defineEmits",
    },
    {
        "id": "angular",
        "name": "Angular 17",
        "monaco_language": "typescript",
        "category": "Frontend",
        "ai_context": "Angular 17, standalone components, signals, control flow, injection tokens, RxJS",
    },
    {
        "id": "svelte",
        "name": "Svelte 5",
        "monaco_language": "javascript",
        "category": "Frontend",
        "ai_context": "Svelte 5 runes, $state, $derived, $effect, SvelteKit routing, load functions",
    },
    {
        "id": "css",
        "name": "CSS / SCSS",
        "monaco_language": "css",
        "category": "Frontend",
        "ai_context": "Modern CSS, custom properties, container queries, @layer, logical properties, nesting",
    },
    {
        "id": "html",
        "name": "HTML5",
        "monaco_language": "html",
        "category": "Frontend",
        "ai_context": "HTML5 semantics, ARIA, Web Components, custom elements, template element",
    },
    # ── Backend & APIs ─────────────────────────────────────────────────────
    {
        "id": "fastapi",
        "name": "FastAPI (Python)",
        "monaco_language": "python",
        "category": "Backend",
        "ai_context": "FastAPI 0.110+, Pydantic v2, dependency injection, async endpoints, background tasks, OAuth2",
    },
    {
        "id": "nodejs",
        "name": "Node.js (Express)",
        "monaco_language": "javascript",
        "category": "Backend",
        "ai_context": "Node.js 20+, Express 5, middleware chains, streaming, worker_threads, cluster",
    },
    {
        "id": "graphql",
        "name": "GraphQL (SDL)",
        "monaco_language": "graphql",
        "category": "Backend",
        "ai_context": "GraphQL schema design, resolvers, mutations, subscriptions, federation, DataLoader",
    },
    {
        "id": "grpc",
        "name": "gRPC / Protobuf",
        "monaco_language": "proto",
        "category": "Backend",
        "ai_context": "Protocol Buffers 3, service definitions, streaming RPCs, metadata, deadlines",
    },
    {
        "id": "django",
        "name": "Django",
        "monaco_language": "python",
        "category": "Backend",
        "ai_context": "Django 5, ORM, class-based views, signals, middleware, channels, Celery integration",
    },
    # ── Data & SQL ─────────────────────────────────────────────────────────
    {
        "id": "sql",
        "name": "SQL (ANSI / PostgreSQL)",
        "monaco_language": "sql",
        "category": "Data",
        "ai_context": "ANSI SQL, PostgreSQL 16, window functions, CTEs, EXPLAIN ANALYZE, partitioning, JSONB",
    },
    {
        "id": "snowflake",
        "name": "Snowflake SQL",
        "monaco_language": "sql",
        "category": "Data",
        "ai_context": "Snowflake SQL, VARIANT, FLATTEN, PARSE_JSON, Snowpark, Time Travel, shares, stages",
    },
    {
        "id": "bigquery",
        "name": "BigQuery SQL",
        "monaco_language": "sql",
        "category": "Data",
        "ai_context": "BigQuery standard SQL, ARRAY_AGG, STRUCT, partitioned tables, ML.PREDICT, geography functions",
    },
    {
        "id": "databricks",
        "name": "Databricks (PySpark)",
        "monaco_language": "python",
        "category": "Data",
        "ai_context": "Databricks Runtime, PySpark 3.5, Delta Lake, Unity Catalog, DLT pipelines, Photon, MLflow",
    },
    {
        "id": "pyspark",
        "name": "PySpark",
        "monaco_language": "python",
        "category": "Data",
        "ai_context": "PySpark DataFrames, RDD operations, Spark SQL, UDFs, streaming, Catalyst optimizer",
    },
    {
        "id": "dbt",
        "name": "dbt (SQL + Jinja)",
        "monaco_language": "sql",
        "category": "Data",
        "ai_context": "dbt Core 1.8+, models, sources, tests, macros, Jinja2, ref(), source(), incremental models",
    },
    {
        "id": "pandas",
        "name": "Pandas / Polars",
        "monaco_language": "python",
        "category": "Data",
        "ai_context": "Pandas 2.0 copy-on-write, Polars lazy API, groupby, merge, pivot, datetime handling",
    },
    {
        "id": "airflow",
        "name": "Apache Airflow",
        "monaco_language": "python",
        "category": "Data",
        "ai_context": "Airflow 2.9+, DAGs, operators, sensors, XComs, TaskFlow API, dynamic task mapping",
    },
    # ── Cloud & Infrastructure ─────────────────────────────────────────────
    {
        "id": "terraform",
        "name": "Terraform / HCL",
        "monaco_language": "hcl",
        "category": "IaC",
        "ai_context": "Terraform 1.8+, providers, modules, state management, workspace, for_each, dynamic blocks, Terragrunt",
    },
    {
        "id": "pulumi",
        "name": "Pulumi (Python/TS)",
        "monaco_language": "python",
        "category": "IaC",
        "ai_context": "Pulumi 3+, stacks, resources, config, secrets, component resources, dynamic providers",
    },
    {
        "id": "cloudformation",
        "name": "AWS CloudFormation",
        "monaco_language": "yaml",
        "category": "IaC",
        "ai_context": "CloudFormation templates, intrinsic functions, conditions, mappings, nested stacks, SAM",
    },
    {
        "id": "bicep",
        "name": "Azure Bicep",
        "monaco_language": "bicep",
        "category": "IaC",
        "ai_context": "Azure Bicep, modules, parameters, conditions, loops, resource symbolicName, deployment scripts",
    },
    {
        "id": "cdk",
        "name": "AWS CDK (Python/TS)",
        "monaco_language": "typescript",
        "category": "IaC",
        "ai_context": "AWS CDK v2, constructs, stacks, context, aspects, custom resources, L1/L2/L3 constructs",
    },
    # ── Containerization & Orchestration ──────────────────────────────────
    {
        "id": "dockerfile",
        "name": "Dockerfile",
        "monaco_language": "dockerfile",
        "category": "DevOps",
        "ai_context": "Dockerfile best practices, multi-stage builds, layer caching, BuildKit, COPY --link, health checks",
    },
    {
        "id": "docker_compose",
        "name": "Docker Compose",
        "monaco_language": "yaml",
        "category": "DevOps",
        "ai_context": "Docker Compose v3.8+, services, volumes, networks, depends_on, healthcheck, profiles",
    },
    {
        "id": "kubernetes",
        "name": "Kubernetes YAML",
        "monaco_language": "yaml",
        "category": "DevOps",
        "ai_context": "Kubernetes 1.29+, Deployments, Services, ConfigMaps, Secrets, HPA, PDB, NetworkPolicy, RBAC",
    },
    {
        "id": "helm",
        "name": "Helm Charts",
        "monaco_language": "yaml",
        "category": "DevOps",
        "ai_context": "Helm 3, chart structure, values.yaml, templates, helpers, hooks, library charts, OCI registry",
    },
    {
        "id": "kustomize",
        "name": "Kustomize",
        "monaco_language": "yaml",
        "category": "DevOps",
        "ai_context": "Kustomize overlays, patches, generators, transformers, components, patchesStrategicMerge",
    },
    # ── CI/CD & GitOps ─────────────────────────────────────────────────────
    {
        "id": "github_actions",
        "name": "GitHub Actions",
        "monaco_language": "yaml",
        "category": "CI/CD",
        "ai_context": "GitHub Actions workflows, jobs, steps, matrix strategy, reusable workflows, environments, OIDC",
    },
    {
        "id": "gitlab_ci",
        "name": "GitLab CI/CD",
        "monaco_language": "yaml",
        "category": "CI/CD",
        "ai_context": "GitLab CI pipelines, stages, jobs, rules, artifacts, cache, DAG, include, extends",
    },
    {
        "id": "jenkins",
        "name": "Jenkinsfile (Groovy)",
        "monaco_language": "groovy",
        "category": "CI/CD",
        "ai_context": "Jenkins declarative pipeline, stages, agents, post, parameters, shared libraries, Blue Ocean",
    },
    {
        "id": "argocd",
        "name": "ArgoCD / GitOps",
        "monaco_language": "yaml",
        "category": "CI/CD",
        "ai_context": "ArgoCD Application manifests, sync policy, health checks, hooks, ApplicationSet, Argo Rollouts",
    },
    # ── Monitoring & Config ────────────────────────────────────────────────
    {
        "id": "ansible",
        "name": "Ansible Playbook",
        "monaco_language": "yaml",
        "category": "Config",
        "ai_context": "Ansible 9+, playbooks, roles, handlers, vars, templates (Jinja2), collections, AWX",
    },
    {
        "id": "prometheus",
        "name": "Prometheus / PromQL",
        "monaco_language": "promql",
        "category": "Monitoring",
        "ai_context": "PromQL queries, recording rules, alerting rules, metric types, labels, functions, subqueries",
    },
    {
        "id": "regex",
        "name": "Regular Expressions",
        "monaco_language": "regexp",
        "category": "Scripting",
        "ai_context": "PCRE regex, lookahead, lookbehind, named groups, backreferences, possessive quantifiers",
    },
    # ── AI / ML ────────────────────────────────────────────────────────────
    {
        "id": "langchain",
        "name": "LangChain (Python)",
        "monaco_language": "python",
        "category": "AI/ML",
        "ai_context": "LangChain 0.2+, chains, agents, tools, memory, LangGraph, LCEL, retrieval, streaming",
    },
    {
        "id": "mlflow",
        "name": "MLflow",
        "monaco_language": "python",
        "category": "AI/ML",
        "ai_context": "MLflow tracking, models, registry, serving, autolog, pyfunc, projects, recipes",
    },
    {
        "id": "dask",
        "name": "Dask",
        "monaco_language": "python",
        "category": "AI/ML",
        "ai_context": "Dask dataframes, bags, arrays, distributed scheduler, delayed, futures, Dask-ML",
    },
    # ── Networking & Security ──────────────────────────────────────────────
    {
        "id": "nginx",
        "name": "Nginx Config",
        "monaco_language": "nginx",
        "category": "Networking",
        "ai_context": "Nginx server blocks, location directives, proxy_pass, SSL, rate limiting, upstream, lua",
    },
    {
        "id": "yaml",
        "name": "YAML (Generic)",
        "monaco_language": "yaml",
        "category": "Config",
        "ai_context": "YAML 1.2 spec, anchors, aliases, multi-line strings, complex keys, merge keys",
    },
    {
        "id": "json",
        "name": "JSON / JSON Schema",
        "monaco_language": "json",
        "category": "Config",
        "ai_context": "JSON Schema draft-07/2020-12, $ref, allOf, oneOf, additionalProperties, validation",
    },
    {
        "id": "toml",
        "name": "TOML",
        "monaco_language": "toml",
        "category": "Config",
        "ai_context": "TOML 1.0, tables, arrays of tables, inline tables, datetime, pyproject.toml patterns",
    },
    {
        "id": "makefile",
        "name": "Makefile",
        "monaco_language": "makefile",
        "category": "Scripting",
        "ai_context": "GNU Make, phony targets, automatic variables, pattern rules, functions, prerequisites, parallel",
    },
    # ── Legacy & Specialized ──────────────────────────────────────────────
    {
        "id": "ruby",
        "name": "Ruby / Rails",
        "monaco_language": "ruby",
        "category": "General",
        "ai_context": "Ruby 3.3, Rails 7.1, active_record, active_support, blocks, procs, mixins, RSpec",
    },
    {
        "id": "php",
        "name": "PHP (Laravel/Symfony)",
        "monaco_language": "php",
        "category": "General",
        "ai_context": "PHP 8.3, Laravel 11, types, fibers, attributes, readonly classes, composer, artisan",
    },
    {
        "id": "swift",
        "name": "Swift",
        "monaco_language": "swift",
        "category": "Mobile",
        "ai_context": "Swift 5.10, SwiftUI, async/await, actors, optionals, generics, property wrappers",
    },
    {
        "id": "objectivec",
        "name": "Objective-C",
        "monaco_language": "objective-c",
        "category": "Mobile",
        "ai_context": "Objective-C 2.0, ARC, blocks, categories, protocols, runtime, Foundation framework",
    },
    {
        "id": "r",
        "name": "R (Data Science)",
        "monaco_language": "r",
        "category": "Data",
        "ai_context": "R 4.4, tidyverse, ggplot2, data.table, dplyr, Shiny, vectorization, pipe operator",
    },
    {
        "id": "julia",
        "name": "Julia",
        "monaco_language": "julia",
        "category": "Data",
        "ai_context": "Julia 1.10, multiple dispatch, metaprogramming, Flux.jl, DataFrames.jl, broadcasting",
    },
    {
        "id": "clojure",
        "name": "Clojure",
        "monaco_language": "clojure",
        "category": "General",
        "ai_context": "Clojure 1.11, Lisp, immutability, atoms, refs, agents, macros, core.async",
    },
    {
        "id": "elixir",
        "name": "Elixir / Phoenix",
        "monaco_language": "elixir",
        "category": "Backend",
        "ai_context": "Elixir 1.16, Erlang/OTP, BEAM, processes, supervisors, pattern matching, Phoenix LiveView",
    },
    {
        "id": "haskell",
        "name": "Haskell",
        "monaco_language": "haskell",
        "category": "General",
        "ai_context": "Haskell GHC 9.8, pure functional, monads, type classes, lazy evaluation, GADTs",
    },
    {
        "id": "fortran",
        "name": "Fortran (Modern)",
        "monaco_language": "fortran",
        "category": "Scientific",
        "ai_context": "Modern Fortran (2018), arrays, modules, coarrays, intrinsic functions, LAPACK/BLAS",
    },
    {
        "id": "cobol",
        "name": "COBOL (Enterprise)",
        "monaco_language": "cobol",
        "category": "Legacy",
        "ai_context": "COBOL 85/2002, divisions, sections, paragraphs, copybooks, fixed-format, VSAM",
    },
    {
        "id": "assembly",
        "name": "Assembly (x86/ARM)",
        "monaco_language": "asm",
        "category": "Systems",
        "ai_context": "x86-64 NASM / ARMv8, registers, stack frames, syscalls, SIMD, inline assembly",
    },
    {
        "id": "lua",
        "name": "Lua",
        "monaco_language": "lua",
        "category": "Scripting",
        "ai_context": "Lua 5.4, tables, metatables, coroutines, C API, Luau, Nginx integration",
    },
    {
        "id": "perl",
        "name": "Perl",
        "monaco_language": "perl",
        "category": "Scripting",
        "ai_context": "Perl 5.38, regex mastery, CPAN, references, Moose, subroutines, file handling",
    },
    {
        "id": "crystal",
        "name": "Crystal",
        "monaco_language": "crystal",
        "category": "Systems",
        "ai_context": "Crystal 1.11, Ruby-like syntax, static typing, LLVM, fibers, macros, shards",
    },
    {
        "id": "nim",
        "name": "Nim",
        "monaco_language": "nim",
        "category": "Systems",
        "ai_context": "Nim 2.0, macros, GC, ARC/ORC, pragmas, C/C++ backend, templates",
    },
    {
        "id": "zig",
        "name": "Zig",
        "monaco_language": "zig",
        "category": "Systems",
        "ai_context": "Zig 0.12, comptime, no hidden control flow, error union, allocators, C interop",
    },
    {
        "id": "solidity",
        "name": "Solidity (Ethereum)",
        "monaco_language": "solidity",
        "category": "Web3",
        "ai_context": "Solidity 0.8.25, smart contracts, EVM, gas optimization, events, modifiers, inheritance",
    },
    {
        "id": "vyper",
        "name": "Vyper (Pythonic Web3)",
        "monaco_language": "python",
        "category": "Web3",
        "ai_context": "Vyper 0.3.10, security-first smart contracts, overflow protection, reentrancy guards",
    },
    {
        "id": "move",
        "name": "Move (Aptos/Sui)",
        "monaco_language": "rust",
        "category": "Web3",
        "ai_context": "Move language, resources, abilities, modules, formal verification, Aptos/Sui framework",
    },
    {
        "id": "powershell_7",
        "name": "PowerShell 7 Core",
        "monaco_language": "powershell",
        "category": "Scripting",
        "ai_context": "PowerShell 7, pwsh, cross-platform, parallel foreach, ternary operators",
    },
    {
        "id": "bash_posix",
        "name": "Bash (Strict POSIX)",
        "monaco_language": "shell",
        "category": "Scripting",
        "ai_context": "POSIX shell compliance, no bashisms, sh, dash, portability, exit codes",
    },
    {
        "id": "sql_server",
        "name": "T-SQL (SQL Server)",
        "monaco_language": "sql",
        "category": "Data",
        "ai_context": "Transact-SQL, SQL Server 2022, stored procedures, triggers, window functions, temp tables",
    },
    {
        "id": "oracle_sql",
        "name": "PL/SQL (Oracle)",
        "monaco_language": "sql",
        "category": "Data",
        "ai_context": "PL/SQL, Oracle 23c, packages, cursors, collections, bulk collect, materialized views",
    },
    {
        "id": "mysql",
        "name": "MySQL / MariaDB",
        "monaco_language": "sql",
        "category": "Data",
        "ai_context": "MySQL 8.0, InnoDB, indexes, partitioning, replication, stored routines, GIS",
    },
    {
        "id": "recoil",
        "name": "Recoil / Jotai (State)",
        "monaco_language": "typescript",
        "category": "Frontend",
        "ai_context": "Recoil state management, atoms, selectors, family, Jotai primitives, atomWithStorage",
    },
    {
        "id": "redux",
        "name": "Redux Toolkit",
        "monaco_language": "typescript",
        "category": "Frontend",
        "ai_context": "Redux Toolkit, slices, thunks, RTK Query, selectors, immutability-helper",
    },
    {
        "id": "mongodb",
        "name": "MongoDB (MQL)",
        "monaco_language": "javascript",
        "category": "Data",
        "ai_context": "MongoDB 7.0, aggregation pipeline, indexes, sharding, atlas search, transactions",
    },
    {
        "id": "redis",
        "name": "Redis Commands",
        "monaco_language": "redis",
        "category": "Data",
        "ai_context": "Redis 7.2, data structures, Lua scripts, modules, streams, pub/sub, sentinel, cluster",
    },
]
