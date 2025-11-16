# Devise: Agentic Government Council 

## 🏛️Project overview

This project addresses the critical collapse in public trust caused by opaque decision-making. When AI agents operate as "black boxes," they amplify this problem.

Our solution is a framework built on three core pillars:

The Inner Monologue: We use a GovAgent that produces a detailed, step-by-step trace of its reasoning, tool calls, and observations for every decision it makes.

The Audit Dashboard: We provide tools to visualize this complex trace as an interactive graph (trace_analysis.html) and a web dashboard (via a Flask server) for easy, non-technical exploration.

The Hybrid Failure Judge: This is a powerful "critic" system that uses an LLM to automatically audit the agent's trace. It combines two methods:

Find the 'Who' (Culprit Detection): An auditor can ask a natural language question (e.g., "Who was assigned this task?"), and the judge finds the exact message(s) in the trace that provide the answer. (See find_issue_origin)

Find the 'When' (Error Detection): The judge automatically scans the trace for logical failures or deviations from the original request, pinpointing the "decisive error step" without needing a human query. (See failure_analysis)

This repository contains the core Python code to run the GovAgent and, more importantly, the Hybrid Failure Judge to analyze its outputs.
## Setup instructions

## 🏛️ Project Overview

This project addresses the critical collapse in public trust caused by opaque decision-making. When AI agents operate as "black boxes," they amplify this problem.

Our solution is a framework built on three core pillars:

1.  **The Inner Monologue:** We use a `GovAgent` that produces a detailed, step-by-step trace of its reasoning, tool calls, and observations for every decision it makes.
2.  **The Audit Dashboard:** We provide tools to visualize this complex trace as an interactive graph (`trace_analysis.html`) and a web dashboard (via a Flask server) for easy, non-technical exploration.
3.  **The Hybrid Failure Judge:** This is a powerful "critic" system that uses an LLM to automatically audit the agent's trace. It combines two methods:
    * **Find the 'Who' (Culprit Detection):** An auditor can ask a natural language question (e.g., "Who was assigned this task?"), and the judge finds the *exact* message(s) in the trace that provide the answer. (See `find_issue_origin`)
    * **Find the 'When' (Error Detection):** The judge automatically scans the trace for logical failures or deviations from the original request, pinpointing the "decisive error step" without needing a human query. (See `failure_analysis`)

This repository contains the core Python code to run the `GovAgent` and, more importantly, the `Hybrid Failure Judge` to analyze its outputs.

---
## How to run/test
