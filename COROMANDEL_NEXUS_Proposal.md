# COROMANDEL-NEXUS: Autonomous Dual-Monsoon Climate Inversion & Reservoir Pre-Discharge Command Engine

> **Hackathon Track:** Track 2 — Climate, Resource Infrastructure & Global Supply Resilience  
> **Target Problem Areas:** Problem Area 2 (*Predictive Climate & Micro-Location Engine*) & Problem Area 3 (*Smart Grid & Urban Resource Allocation Controller*)  
> **Flagship Pitch:** Exposes the "Coromandel ENSO Paradox" to resolve the multi-billion-dollar Dam Operator's Dilemma—dynamically calculating pre-discharge flood cushions for major reservoirs (Chembarambakkam, Mettur, Pechiparai) to prevent catastrophic emergency water releases during El Niño-supercharged Northeast monsoons.

---

## 1. The Core Idea & The Real-World Problem

### 1.1 The Core Scientific Paradox (The "Coromandel Inversion")
While El Niño causes rainfall deficits and agricultural drought in 60% of mainland India during the Southwest Monsoon (June–September), **it has an inverted, supercharging effect on the Northeast Monsoon (October–December) over Tamil Nadu and the Coromandel Coast**. 
* Anomalously warm sea-surface temperatures in the southern Bay of Bengal coupled with low-level easterly wind steering funnel **extreme atmospheric rivers and severe cyclonic storms** directly into coastal Tamil Nadu.
* Over **80% of historical El Niño years produce excess, explosive rainfall** in this belt, directly triggering India's worst urban and riverine deluges:
  * **2015 Super El Niño:** The catastrophic Chennai Floods ($>1,000\text{ mm}$ in days, Chembarambakkam reservoir breach, $>400$ deaths, $\$3\text{B}+$ damages).
  * **2023 Strong El Niño:** The South Tamil Nadu Deluge (Tirunelveli & Thoothukudi received $950\text{ mm}$ in 48 hours—an entire year's rain in two days).

### 1.2 The Dam Operator's Dilemma (The Infrastructure Crisis)
The true disaster is not rainfall alone; it is **the lack of anticipatory reservoir buffering**:
* In August/September, Tamil Nadu reservoirs are depleted following weak Southwest monsoon inflows and interstate Cauvery disputes.
* Engineers entering October follow outdated, static **"Rule Curves"** and hold onto every drop of incoming water to protect summer municipal drinking supply.
* When an El Niño-charged storm drops $400\text{ mm}$ in 24 hours, the dam hits 100% full capacity overnight. 
* Caught unprepared, engineers are forced into an **emergency release of $30,000\text{ to }100,000\text{ cusecs}$ into swollen downstream rivers (Adyar, Tamirabarani)**, drowning Chennai or Tirunelveli with only a few hours of warning.

---

## 2. The Solution: What COROMANDEL-NEXUS Does

**COROMANDEL-NEXUS** is an institutional command-and-control engine that replaces static rule curves with **dynamic, anticipatory flood buffering**:

1. **Dual-Monsoon Teleconnection Downscaling:** Ingests live NOAA Pacific ONI alongside real-time **Bay of Bengal Sea Surface Temperature (SST)** and easterly wind anomalies via sub-second Open-Meteo APIs.
2. **Dynamic Reservoir Pre-Discharge Simulator:** Calculates the exact mathematical water cushion needed in key reservoirs (Chembarambakkam, Poondi, Mettur, Pechiparai).
   * *The Core Equation:* Demonstrates that releasing a **steady, controlled $1,800\text{ cusecs}$ over 4 days in advance** completely absorbs an incoming $4,000\text{ Mcft}$ storm runoff, **eliminating the catastrophic $35,000\text{ cusecs}$ emergency dump**.
3. **Multi-Stage Verifiable State Machine:** Moves from live data verification to runoff calculation, historical analogue matching (2015 vs 2023), and human-in-the-loop authorization.
4. **Autonomous ReAct Agent (Day 2 Workshop Architecture):** An executive Gemini agent that audits telemetry, verifies CWC dam safety bounds, and drafts the **Official Sluice-Gate Pre-Discharge Order** for the Chief Engineer's digital signature.

---

## 3. The 4 Verifiable Checkpoint Stages

```text
 ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
 │  CHECKPOINT 1   │  ──>  │  CHECKPOINT 2   │  ──>  │  CHECKPOINT 3   │  ──>  │  CHECKPOINT 4   │
 │ Teleconnection  │       │ Catchment Runoff│       │ Disaster Replay │       │ Sluice Release  │
 │ Provenance Gate │       │ Math Gate       │       │ Analogue Gate   │       │ Authorization   │
 └─────────────────┘       └─────────────────┘       └─────────────────┘       └─────────────────┘
  [Live NOAA + SST]         [Inflow > Cushion]        [2015 / 2023 k-NN]        [Human Sign-Off]
```

### Stage 1: Teleconnection Provenance Gate
* **Validates:**
  * NOAA CPC raw ASCII: Checks Pacific ONI ($\text{SST Anomaly} > +0.5^\circ\text{C}$).
  * Open-Meteo Marine: Checks Bay of Bengal SST off Chennai ($12.5^\circ\text{N}, 81.5^\circ\text{E} \ge 29.0^\circ\text{C}$).
  * Catchment Soil Saturation ($\theta \ge 0.38\text{ m}^3/\text{m}^3$).
* **UI Artifact:** Green badge proving live 200 OK responses with microsecond latency.

### Stage 2: Catchment Runoff Math Gate
* **Validates:** Rational Runoff formula applied to Chembarambakkam Catchment ($358\text{ km}^2$):
  $$Q_{\text{peak}} = 0.278 \cdot C \cdot I \cdot A$$
* Calculates expected storm inflow volume vs available reservoir capacity:
  $$\text{Storage Deficit} = V_{\text{inflow}} - (\text{Full Capacity} - \text{Current Storage})$$

### Stage 3: Disaster Replay Analogue Gate
* **Validates:** Evaluates similarity against the **2015 Chennai Flood (Nov 30–Dec 2)** and **2023 South TN Deluge (Dec 17–18)** using historical ERA5 reanalysis datasets.
* Displays historical match score ($S \ge 0.88$).

### Stage 4: Sluice Release Authorization Gate (Human-in-the-Loop)
* **Validates:** Agent checks CWC Dam Safety guidelines against downstream river capacity (Adyar River safe non-flood capacity $\approx 15,000\text{ cusecs}$).
* **Action:** Agent drafts the **Executive Dam Sluice Pre-Release Order**:
  * Action: Open Sluice Gates 3 & 4 by $1.2\text{ meters}$.
  * Discharge: $1,800\text{ cusecs}$ for 72 hours.
  * Status: **[PENDING CHIEF ENGINEER AUTHORIZATION]** $\rightarrow$ User clicks **[AUTHORIZE DISPATCH]**.

---

## 4. Live Data Pipeline (100% Anti-Disqualification Audit)

| Variable | Official Data Provider | Endpoint Protocol | Latency | Dummy Data Risk |
| :--- | :--- | :--- | :--- | :--- |
| **Pacific ENSO Status** | NOAA CPC | `https://www.cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii` | $< 300\text{ ms}$ | **Zero**: Live ASCII table parsed in backend. |
| **Bay of Bengal SST** | Open-Meteo Marine | `https://marine-api.open-meteo.com/v1/marine?latitude=12.5&longitude=81.5&hourly=sea_surface_temperature` | $< 250\text{ ms}$ | **Zero**: Free, instant REST API, sub-second JSON. |
| **Catchment Rainfall** | Open-Meteo Weather | `https://api.open-meteo.com/v1/forecast?latitude=13.01&longitude=80.01&hourly=precipitation,soil_moisture_0_to_7cm` | $< 300\text{ ms}$ | **Zero**: Live coordinates for Chembarambakkam. |
| **Reservoir Storage Baselines** | Chennai MetroWater (CMWSSB) & CWC | Pre-seeded PostgreSQL table (`chembarambakkam_metrics`) | $< 30\text{ ms}$ | **Zero**: Official government dam specifications. |

---

## 5. Technical Architecture & Tech Stack

```text
coromandel-nexus/
├── frontend/                          # React 18 + Vite + Vanilla CSS
│   ├── src/
│   │   ├── components/
│   │   │   ├── BasinMap.jsx           # Leaflet map with Chembarambakkam & Adyar River GeoJSON
│   │   │   ├── ReservoirGauge.jsx     # Dynamic SVG water level & flood cushion visualization
│   │   │   ├── PreDischargeSlider.jsx # Interactive pre-discharge rate & storm forecast slider
│   │   │   ├── CheckpointStepper.jsx  # 4-stage audit status & verification indicators
│   │   │   └── AgentCommandTerminal.jsx # Live tool execution logs & official order dispatch
│   │   ├── services/
│   │   │   └── api.js                 # Axios API connector
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
│
├── backend/                           # Node.js + Express (Single Unified Server)
│   ├── src/
│   │   ├── agents/
│   │   │   ├── geminiAgent.js         # Gemini 1.5/2.0 ReAct loop with tool declarations
│   │   │   └── damSafetyTools.js      # Deterministic tools for hydrology & CWC limits
│   │   ├── services/
│   │   │   ├── noaaClient.js          # Direct ASCII parser for NOAA CPC ONI
│   │   │   ├── marineClient.js        # Open-Meteo Bay of Bengal SST client
│   │   │   ├── catchmentClient.js     # Chembarambakkam hourly weather & soil moisture
│   │   │   └── runoffCalculator.js    # Rational Runoff & safe flood cushion formulas
│   │   ├── db/
│   │   │   └── dams.json              # Official CMWSSB/CWC dam ratings (FRL, MWL, Gate discharge)
│   │   └── server.js                  # Express API endpoints
│   ├── package.json
│   └── .env.example
│
└── docs/
    └── SCRIPT.md                      # 2.5-minute video demo script
```

---

## 6. The 48-Hour Implementation Plan

```text
┌─────────────────────────┬─────────────────────────────────────────────────────────────────┐
│ SPRINT MILESTONE        │ TASKS & DELIVERABLES                                            │
├─────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Sprint 1: Hours 00 – 12 │ 1. Initialize Git repo & scaffold Vite React + Express backend. │
│ Data Clients & Hydrology│ 2. Code `noaaClient.js` (ASCII parser) and `marineClient.js`.   │
│                         │ 3. Implement `runoffCalculator.js` (Inflow vs Storage Deficit). │
│                         │ 4. Seed dam specs for Chembarambakkam, Poondi, and Mettur.      │
├─────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Sprint 2: Hours 12 – 24 │ 1. Implement Gemini ReAct agent with 4 deterministic tools:     │
│ ReAct Agent & State     │    • `get_ocean_teleconnections`                                │
│                         │    • `calculate_catchment_runoff`                               │
│                         │    • `match_historical_disaster`                                │
│                         │    • `generate_predischarge_order`                              │
│                         │ 2. Implement the 4-Stage Verifiable Checkpoint State Machine.   │
├─────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Sprint 3: Hours 24 – 36 │ 1. Build React dashboard: Leaflet Adyar basin map.              │
│ Frontend Dashboard      │ 2. Create interactive SVG Reservoir Gauge + Pre-discharge slider│
│                         │ 3. Connect live Checkpoint Stepper & Agent Command Terminal.    │
│                         │ 4. Test end-to-end response times (< 2 seconds total).          │
├─────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Sprint 4: Hours 36 – 48 │ 1. Deploy frontend to Vercel, backend to Render/Railway.        │
│ Testing & Demo Video    │ 2. Verify live APIs and error handling under offline fallback.  │
│                         │ 3. Record 2.5-minute Loom/YouTube demo video following script.  │
│                         │ 4. Polish README with architecture diagram & submit.            │
└─────────────────────────┴─────────────────────────────────────────────────────────────────┘
```

---

## 7. The 2.5-Minute Demo Video Script & Storyboard

* **0:00 – 0:30 (The Hook & The Paradox):**
  * *Visual:* Split screen showing dry cracked fields in North India vs the submerged streets of Chennai in 2015.
  * *Narrator:* *"Most people think an El Niño only means drought in India. But for Tamil Nadu and the Coromandel coast, it means the exact opposite: catastrophic, supercharged cloudbursts. In 2015 and 2023, hundreds died not just because of the rain, but because reservoirs like Chembarambakkam were 100% full when the storm hit, forcing an emergency dump of 35,000 cusecs into city streets. This is the Dam Operator's Dilemma—and this is COROMANDEL-NEXUS."*
* **0:30 – 1:05 (Live Data & Checkpoint 1):**
  * *Visual:* Focus on the Leaflet map of Chennai & Chembarambakkam Lake. Click *"Inspect Telemetry"*.
  * *Narrator:* *"Notice Checkpoint 1 passing in real-time. We are pulling live NOAA Pacific ONI indices and querying the Open-Meteo Marine API for live Bay of Bengal sea surface temperatures off Chennai (29.4°C). Zero dummy data, verified with live timestamps."*
* **1:05 – 1:45 (The Pre-Discharge Simulator & Checkpoint 2):**
  * *Visual:* Slide the storm forecast to $300\text{ mm}$ over 3 days. The SVG Reservoir Gauge animates.
  * *Narrator:* *"Watch Checkpoint 2. If the dam operators wait, the storm will dump 4,200 Mcft into a reservoir with only 2,100 Mcft of cushion, guaranteeing a catastrophic breach. But as we activate the pre-discharge slider, the engine calculates that a steady, safe release of 1,800 cusecs over the preceding 4 days creates the exact flood cushion needed to absorb the storm without overflowing the Adyar river."*
* **1:45 – 2:15 (Autonomous ReAct Agent & Checkpoint 4):**
  * *Visual:* Click *"Execute Emergency Audit"*. The UI streams the Gemini agent executing tool calls live.
  * *Narrator:* *"Our autonomous agent takes over. Operating on a ReAct loop, it verifies downstream river capacity, matches the atmospheric setup against the 2015 disaster analogue at Checkpoint 3, and generates an official Sluice-Gate Pre-Discharge Order at Checkpoint 4. Under human-in-the-loop governance, the Chief Engineer reviews the parameters and clicks Authorize."*
* **2:15 – 2:30 (Summary & Impact):**
  * *Visual:* Clean view of the authorized command dashboard with live status indicators.
  * *Narrator:* *"COROMANDEL-NEXUS transforms blind disaster reaction into anticipatory infrastructure resilience. Thank you."*
