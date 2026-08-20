#!/usr/bin/env python3
"""
Second seed graph ("Priya") for the graph-2 replication check (Phase A).

Purpose: test whether the graph-vs-flat_list decisiveness effect generalizes
beyond the single "Alex" persona in poc_compare.DEMO_GRAPH, or is an artifact
of that specific graph. Same structural format (domain -> theme -> concept
chains, same weight formula) and a genuinely different domain mix / weight
shape - not a reskin. Full design (node/weight list, ground-truth ranking,
query set) was reviewed and approved before this file was used for any live
run; see the conversation record, not reproduced here.

This module does NOT modify poc_compare.py's DEMO_GRAPH/PRIORITY_QUERIES/
_seed_demo_graph in any way - it is a parallel, independent seed + query set
sharing only the eval DB path pattern and weight formula, imported
separately by poc_compare_multimodel_graph2.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import db
from db import init_db, add_node, add_edge, get_connection

EVAL_DB_PATH_2 = os.path.join(HERE, "poc_eval_graph2.db")

DEMO_USER_2 = "Priya"
DEMO_GRAPH_2 = [
    {
        "domain": "Client Design Work",
        "domain_weight": 78,
        "themes": [
            {
                "name": "Active Client Projects",
                "weight": 74,
                "chain": [
                    "Brand identity project deadline for local bakery",
                    "Website redesign for nonprofit client",
                    "New client onboarding backlog",
                    "Client feedback revision round",
                    "Invoice follow-up for overdue client",
                    "Portfolio case study writeup",
                    "Referral outreach to past clients",
                ],
            },
            {
                "name": "Design Skill Development",
                "weight": 68,
                "chain": [
                    "Figma advanced prototyping course",
                    "Typography study deep dive",
                    "Motion design experimentation",
                    "Accessibility in UI design research",
                ],
            },
        ],
    },
    {
        "domain": "Family & Caregiving",
        "domain_weight": 72,
        "themes": [
            {
                "name": "Parent's Care Coordination",
                "weight": 67,
                "chain": [
                    "Mom's cardiology appointment follow-up",
                    "In-home care aide search",
                    "Medicare paperwork review",
                    "Family caregiving schedule coordination",
                    "Mom's medication management system",
                ],
            },
            {
                "name": "Kids' School Transition",
                "weight": 60,
                "chain": [
                    "Middle school enrollment research",
                    "After-school program evaluation",
                    "Kid's reading tutor search",
                    "Parent-teacher conference prep",
                ],
            },
        ],
    },
    {
        "domain": "Studio Business Operations",
        "domain_weight": 70,
        "themes": [
            {
                "name": "Financial Planning",
                "weight": 66,
                "chain": [
                    "Quarterly tax estimate prep",
                    "Studio pricing strategy revision",
                    "Business savings buffer goal",
                    "Expense tracking system cleanup",
                ],
            },
            {
                "name": "Studio Growth",
                "weight": 58,
                "chain": [
                    "Hiring a part-time contractor",
                    "Client intake process automation",
                    "Studio website SEO improvement",
                    "Local business networking events",
                ],
            },
        ],
    },
    {
        "domain": "Creative Practice",
        "domain_weight": 55,
        "themes": [
            {
                "name": "Ceramics Hobby",
                "weight": 50,
                "chain": [
                    "Wheel-throwing technique practice",
                    "Glaze chemistry experimentation",
                    "Community studio membership renewal",
                ],
            },
        ],
    },
    {
        "domain": "Personal Health",
        "domain_weight": 40,
        "themes": [
            {
                "name": "Health & Recovery",
                "weight": 36,
                "chain": [
                    "Physical therapy for wrist strain",
                    "Sleep schedule regularization",
                    "Annual physical checkup scheduling",
                ],
            },
        ],
    },
]

# 12 priority queries. 10 of these are byte-identical to poc_compare.
# PRIORITY_QUERIES (query instrument held constant across graphs); only #4
# and #11 (forced-choice queries naming graph-1-specific entities) are
# replaced with graph-2-appropriate equivalents.
PRIORITY_QUERIES_2 = [
    "What's my top priority right now?",
    "What should I focus on next?",
    "If I could only work on one thing this week, what should it be?",
    "Between the bakery brand identity project and my mom's care coordination, which should I prioritize?",
    "What's the single most important thing I should be doing today?",
    "Rank my current projects from most to least urgent.",
    "I only have a few free hours this weekend - what should I spend them on?",
    "What's holding me back the most right now?",
    "Which of my interests deserves the most attention this month?",
    "What's the one thing that, if I finished it, would unlock the most progress?",
    "Should I focus on client work or my ceramics practice first?",
    "What's the highest-leverage use of my time this week?",
]


def _seed_demo_graph_2():
    if os.path.exists(EVAL_DB_PATH_2):
        os.remove(EVAL_DB_PATH_2)
    db.DB_PATH = EVAL_DB_PATH_2
    init_db()

    def set_weight(label: str, weight: float):
        with get_connection() as conn:
            conn.execute("UPDATE nodes SET weight = ? WHERE label = ?", (weight, label))

    def add_chain(parent: str, titles: list[str], base_weight: float):
        prev = parent
        for i, title in enumerate(titles):
            w = base_weight * (1 - 0.05 * i)
            add_node(title, node_type="concept")
            set_weight(title, round(w, 1))
            add_edge(prev, title)
            prev = title

    add_node(DEMO_USER_2, node_type="user")
    set_weight(DEMO_USER_2, 100.0)

    for d in DEMO_GRAPH_2:
        add_node(d["domain"], node_type="domain")
        set_weight(d["domain"], d["domain_weight"])
        add_edge(DEMO_USER_2, d["domain"])
        for t in d["themes"]:
            add_node(t["name"], node_type="theme")
            set_weight(t["name"], t["weight"])
            add_edge(d["domain"], t["name"])
            add_chain(t["name"], t["chain"], t["weight"])
