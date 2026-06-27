# Aegis — Project Context & Goals

> A taint-aware agentic moderator and sandbox framework for defending LLM agents against prompt injection attacks.

**Type:** Minor Project (Bachelor of Engineering in Software Engineering)
**Institution:** Nepal College of Information Technology, Pokhara University
**Team:** Pawan Sharma (231625) · Asmita Katwal (231609) · Prashanna Pokhrel (231628)
**Supervisor:** Manil Baidya
**Duration:** ~1 month (four weekly sprints)

---

## 1. In one paragraph

LLM agents now act on the world through tools (email, web, files, code), but a language model reads all text as a single stream and cannot reliably separate *trusted instructions* from *untrusted data*. This makes them vulnerable to **prompt injection** — malicious instructions hidden inside the content an agent reads, which hijack its behavior. Aegis is a defensive framework that wraps a tool-using agent in four cooperating layers — a moderator, taint tracking, a policy gate, and a sandbox — and measures, on a recognized benchmark, how much this reduces attacks while keeping the agent useful.

---

## 2. The problem we are solving

- An LLM has no hard boundary between "instructions" and "data" — both are just text, and the separation is statistical, not enforced.
- **Prompt injection** exploits this: adversarial text overrides the agent's intended task.
  - *Direct:* the malicious user types the attack.
  - *Indirect (the dangerous kind):* the attack is hidden in content the agent reads while doing a normal task — a web page, a document, an email — so it acts for the attacker without the user knowing.
- Risk peaks with the **"lethal trifecta"** — when an agent simultaneously has (1) access to private data, (2) exposure to untrusted content, and (3) the ability to communicate externally. An attacker can then make it read secrets and send them out.
- It is the **#1 risk** in the OWASP Top 10 for LLM applications, with reported attack success rates above 80% on agentic systems, and no complete fix exists — model-level defenses are necessary but not sufficient, which is why a **system-level** defense is needed.

---

## 3. What we want to do (the build)

Build **Aegis**: a defense-in-depth layer around a tool-using LLM agent, made of four parts.

1. **Agentic Moderator** — intercepts every proposed tool call; combines deterministic policy rules with a lightweight LLM-as-judge risk score; decides **allow / block / escalate**.
2. **Taint Tracking (coarse-grained)** — labels data as trusted or untrusted and propagates the labels: once any untrusted tool output enters the context, downstream content is treated as tainted.
3. **Policy Gate** — enforces the lethal-trifecta rule: block or escalate (to a human) any high-risk action (e.g., external send / exfiltration) that depends on tainted data.
4. **Sandbox** — runs all tool execution in isolation, so even an injection that slips past the moderator cannot reach the host system or leak private data.

**How it works (request to action):** user request (trusted) → planner proposes a tool call → moderator checks taint level + risk → policy gate allows / blocks / escalates → sandbox executes allowed calls → results labeled by source (untrusted = tainted) → back into the loop. Every decision is logged.

---

## 4. What we want to achieve (goals)

**Primary goal:** demonstrate, with measurable evidence on a recognized benchmark, that a layered system-level defense substantially reduces prompt-injection success while preserving the agent's usefulness.

**Specific objectives:**

1. Implement an agentic moderator that screens inputs, tool outputs, and actions (allow / block / escalate).
2. Implement coarse-grained taint tracking and label propagation.
3. Enforce a lethal-trifecta policy gate on high-risk actions over untrusted data.
4. Integrate a sandbox so tool execution cannot reach the host or leak data.
5. Evaluate on the **AgentDojo** benchmark — measuring attack reduction and retained task utility — with ablation studies isolating each layer's contribution.

---

## 5. What success looks like (criteria)

Measured on AgentDojo against an undefended baseline:

| Metric | Target direction |
|---|---|
| Attack Success Rate (ASR) | Substantially reduced |
| Benign Task Utility | Largely preserved |
| False-Positive / over-block rate | Low |
| Latency overhead | Acceptable |

A trivial "block everything" defense fails because utility collapses; Aegis only counts as successful if it cuts attacks **and** keeps the agent usable. Even a partial result is a valid outcome if it is honestly measured and analyzed (the ablations show which layer helped).

---

## 6. Scope & non-goals

**In scope:** text-based, tool-using LLM agents; the four-layer defense; AgentDojo evaluation; a lightweight dashboard visualizing trust labels and blocked attacks.

**Out of scope (stated as limitations / future work):**

- Multimodal injection (attacks hidden in images or audio).
- Fine-grained, interpreter-level data-flow tracking (we use **coarse-grained** on purpose, for feasibility — CaMeL-style fine-grained tracking is future work).
- Production hardening; we build a reproducible prototype, not a shippable product.
- Building sandbox isolation from scratch — we use a third-party sandbox service.
- Defending against attacks beyond what the benchmark covers.

---

## 7. Approach & methodology

- **Agile-inspired:** four weekly sprints, each producing a working increment; riskiest parts (benchmark integration, taint logic) validated early.
- **Defense in depth:** four independent layers so the failure of one does not compromise the whole. Notably, the final decision relies on deterministic rules and the taint label (not only the judge LLM), and the sandbox contains damage even if moderation is fooled — including the case where the moderator LLM is itself injected.
- **Built on AgentDojo**, not from scratch: AgentDojo provides the agent harness, realistic tool environments, and the injection test cases; we implement Aegis as defense components plugged into its agent pipeline.

---

## 8. Tech stack

- **Language:** Python 3.11+
- **Benchmark / harness:** AgentDojo (`pip install agentdojo`; MIT-licensed; 4 suites — workspace, banking, travel, slack — 97 user tasks and hundreds of injection cases)
- **Reasoning engine:** an LLM via an OpenAI-compatible API (local Ollama for development; a stronger model for final evaluation)
- **Sandbox:** an isolated execution service (micro-VM style isolation)
- **Interface:** a lightweight web dashboard for visualizing decisions
- **Collaboration:** Git + shared repository; Jira for task tracking

---

## 9. Evaluation plan

- **Benchmark:** AgentDojo — realistic tasks plus injection security cases; the defense hooks into the agent loop.
- **Ablations:** four configurations — baseline (no defense), moderator only, sandbox only, combined — to show each layer's contribution.
- **Metrics:** attack success rate, benign task utility, false-positive rate, latency overhead.
- **Reproducibility:** every run logged to a results store so numbers can be regenerated.

---

## 10. Team & responsibilities

| Member | Work-stream | Owns |
|---|---|---|
| **Pawan** | Detection | Agentic moderator, coarse-grained taint tracking, trust-label model |
| **Asmita** | Containment | Sandbox integration, lethal-trifecta policy gate, human-escalation path |
| **Prashanna** | Evaluation | AgentDojo harness, metrics & logging, ablations, dashboard |
| **Shared** | — | Repo & interface contracts, integration, final report & presentation |

**Key interfaces to keep stable:** taint tracker → policy gate (`decide(tool_call, taint_state) → ALLOW / BLOCK / ESCALATE`), and everything → logging.

---

## 11. Timeline (four sprints)

- **Week 1 — Foundations & Baseline:** set up AgentDojo and the environment; measure the undefended baseline; agree repo and interface contracts.
- **Week 2 — Detection:** trust labels, coarse propagation, the LLM-as-judge moderator wired into the agent loop.
- **Week 3 — Containment & Integration:** sandbox, lethal-trifecta policy gate, human escalation; end-to-end integration.
- **Week 4 — Evaluation & Polish:** full benchmark and ablations; dashboard; results, report, and demo.

---

## 12. Key concepts (glossary)

- **Prompt injection** — adversarial text that overrides an agent's intended instructions.
- **Indirect injection** — injection hidden in external content the agent reads mid-task.
- **Lethal trifecta** — private-data access + untrusted content + external communication.
- **Taint tracking** — marking untrusted data and following it through the system to control sensitive operations on it.
- **Coarse-grained taint** — if any untrusted input could have influenced an output, treat the output as tainted (simpler than fine-grained; slightly over-blocks).
- **Policy gate** — rule that blocks/escalates high-risk actions on tainted data.
- **Defense in depth** — layering independent controls so one failure is not catastrophic.
- **Ablation study** — turning components off one at a time to measure each one's contribution.

---

## 13. Data, ethics & licensing

- **No real or personal data:** AgentDojo provides synthetic tasks and synthetic attacks; nothing involves real users' information.
- **No new exploits:** the attack techniques are already public and built into the benchmark; we build and measure *defenses* only.
- **Licensing:** AgentDojo and guardrail tools are open-source, used under their licenses; the LLM is accessed under the provider's API terms. All sources are cited (IEEE).

---

## 14. References (selected)

1. OWASP Foundation, *OWASP Top 10 for Large Language Model Applications*, 2025.
2. S. Willison, *The lethal trifecta for AI agents*, 2025.
3. S. Willison, *The Dual LLM pattern for building AI assistants that can resist prompt injection*, 2023.
4. E. Debenedetti et al., *AgentDojo: A Dynamic Environment to Evaluate Attacks and Defenses for LLM Agents*, NeurIPS 2024 (arXiv:2406.13352).
5. L. Beurer-Kellner et al., *Defeating Prompt Injections by Design (CaMeL)*, 2025 (arXiv:2503.18813).
6. L. Beurer-Kellner et al., *Design Patterns for Securing LLM Agents against Prompt Injections*, 2025.
7. Protect AI, *LLM Guard*; NVIDIA, *NeMo Guardrails* — open-source guardrail toolkits.
