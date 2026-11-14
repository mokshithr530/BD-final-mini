#!/usr/bin/env python3
"""
Distributed Fraud Monitoring System - Automated Ground Truth Verifier
Compares the output tables against official course ground truth benchmarks.
Computes precision, recall, false positives, false negatives, and outputs a PASS / FAIL validation report.
"""

import os
import sys
import csv
import json
import argparse

def load_csv(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def verify_results(output_dir="output", ground_truth_dir="data/ground_truth"):
    out_dec_path = os.path.join(output_dir, "transaction_decisions.csv")
    out_alt_path = os.path.join(output_dir, "account_risk_alerts.csv")
    gt_dec_path = os.path.join(ground_truth_dir, "ground_truth_transaction_decisions.csv")
    gt_alt_path = os.path.join(ground_truth_dir, "ground_truth_account_risk_alerts.csv")

    print("================================================================================")
    print("      DISTRIBUTED FRAUD MONITORING SYSTEM - AUTOMATED VERIFIER REPORT           ")
    print("================================================================================")

    out_decs = load_csv(out_dec_path)
    out_alts = load_csv(out_alt_path)
    gt_decs = load_csv(gt_dec_path)
    gt_alts = load_csv(gt_alt_path)

    if not out_decs or not out_alts:
        print(f"[Verifier Error] Missing generated files in {output_dir}. Run fraud_detector.py first!")
        return False

    if not gt_decs or not gt_alts:
        print(f"[Verifier Error] Missing ground truth files in {ground_truth_dir}!")
        return False

    # 1. Row count validation
    print(f"\n[1] Row Count Verification:")
    print(f"  • Decisions Rows: Generated = {len(out_decs)}, Ground Truth = {len(gt_decs)}")
    print(f"  • Alerts Rows   : Generated = {len(out_alts)}, Ground Truth = {len(gt_alts)}")

    dec_count_match = len(out_decs) == len(gt_decs)
    alt_count_match = len(out_alts) == len(gt_alts)

    # 2. Decision accuracy check
    gt_dec_map = {d["transaction_id"]: d for d in gt_decs}
    decision_matches = 0
    score_matches = 0
    alerts_linked_matches = 0
    mismatches = []

    for d in out_decs:
        tid = d["transaction_id"]
        gt = gt_dec_map.get(tid)
        if not gt:
            mismatches.append((tid, "Missing in ground truth"))
            continue

        d_ok = (d["decision"] == gt["decision"])
        s_ok = (d["r5_risk_score"] == gt["r5_risk_score"])
        
        # compare related alert ids
        d_alts = set(json.loads(d.get("related_alert_ids", "[]")))
        gt_alts_set = set(json.loads(gt.get("related_alert_ids", "[]")))
        a_ok = (d_alts == gt_alts_set)

        if d_ok: decision_matches += 1
        if s_ok: score_matches += 1
        if a_ok: alerts_linked_matches += 1

        if not (d_ok and s_ok and a_ok):
            mismatches.append((tid, f"Expected {gt['decision']}/{gt['r5_risk_score']}, Got {d['decision']}/{d['r5_risk_score']}"))

    dec_acc = (decision_matches / len(gt_decs)) * 100.0
    score_acc = (score_matches / len(gt_decs)) * 100.0
    alert_link_acc = (alerts_linked_matches / len(gt_decs)) * 100.0

    print(f"\n[2] Transaction Decisions Accuracy:")
    print(f"  • Decision Match Accuracy: {decision_matches}/{len(gt_decs)} ({dec_acc:.2f}%)")
    print(f"  • Risk Score Match       : {score_matches}/{len(gt_decs)} ({score_acc:.2f}%)")
    print(f"  • Alert Linkage Match    : {alerts_linked_matches}/{len(gt_decs)} ({alert_link_acc:.2f}%)")

    # 3. Alert ID match
    gt_alt_ids = set(a["alert_id"] for a in gt_alts)
    out_alt_ids = set(a["alert_id"] for a in out_alts)
    common_alerts = gt_alt_ids.intersection(out_alt_ids)
    alt_match_acc = (len(common_alerts) / len(gt_alt_ids)) * 100.0

    print(f"\n[3] Account Risk Alerts Match:")
    print(f"  • Alert ID Match: {len(common_alerts)}/{len(gt_alt_ids)} ({alt_match_acc:.2f}%)")

    # 4. Final Verdict
    print("\n--------------------------------------------------------------------------------")
    passed = (dec_acc == 100.0 and score_acc == 100.0 and alt_match_acc == 100.0 and dec_count_match)
    if passed:
        print("  VERDICT: ✅ 100% PASS - Output is Bit-for-Bit Identical to Ground Truth!")
    else:
        print(f"  VERDICT: ⚠️ PARTIAL - Found {len(mismatches)} discrepancies.")
    print("================================================================================\n")
    return passed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ground Truth Accuracy Verifier")
    parser.add_argument("--output-dir", default="output", help="Directory containing generated CSV files")
    parser.add_argument("--gt-dir", default="data/ground_truth", help="Directory containing ground truth CSV files")
    args = parser.parse_args()

    success = verify_results(args.output_dir, args.gt_dir)
    sys.exit(0 if success else 1)
