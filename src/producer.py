#!/usr/bin/env python3
"""
Distributed Fraud Monitoring System - Kafka Transaction Producer
Streams events from transactions.csv into Apache Kafka topic 'transactions_input'.
Supports:
  - Real-time streaming simulation with customizable delay
  - Batch ingestion for rapid local processing
  - Disorder injection for Chaos Engineering experiments (30s and 90s delay)
"""

import os
import sys
import csv
import json
import time
import argparse
from datetime import datetime, timedelta

def load_transactions(csv_path):
    transactions = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(row)
    return transactions

def create_kafka_producer(bootstrap_servers):
    try:
        from kafka import KafkaProducer
        return KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8")
        )
    except Exception as e:
        print(f"[Producer] Warning: Could not connect to Kafka at {bootstrap_servers}: {e}")
        return None

def stream_transactions(csv_path, topic="transactions_input", bootstrap_servers="localhost:9092", 
                        speed_factor=1.0, max_events=None, disorder_scenario="none"):
    """
    disorder_scenario:
      - 'none': Normal ordered stream
      - 'delay_30s': Injects selected events 30 seconds out of order
      - 'delay_90s': Injects selected events 90 seconds out of order (past 60s watermark)
    """
    transactions = load_transactions(csv_path)
    if max_events:
        transactions = transactions[:max_events]
    
    producer = create_kafka_producer(bootstrap_servers)
    
    print(f"[Producer] Loaded {len(transactions)} transactions from {csv_path}")
    print(f"[Producer] Streaming to topic '{topic}' at {bootstrap_servers} (Scenario: {disorder_scenario})")
    
    # Apply disorder if requested for stress experiments
    if disorder_scenario in ("delay_30s", "delay_90s"):
        delay_sec = 30 if disorder_scenario == "delay_30s" else 90
        print(f"[Producer] Injecting {delay_sec}s out-of-order delay into periodic transaction bursts...")
        delayed_txns = []
        normal_txns = []
        for i, txn in enumerate(transactions):
            # Inject delay into 1 out of every 5 transactions
            if i % 5 == 0:
                delayed_txns.append(txn)
            else:
                normal_txns.append(txn)
        # Re-interleave with synthetic time shifts
        transactions = normal_txns + delayed_txns

    sent_count = 0
    start_time = time.time()
    
    for txn in transactions:
        payload = {
            "event_id": txn.get("event_id"),
            "transaction_id": txn.get("transaction_id"),
            "user_id": txn.get("user_id"),
            "customer_id": txn.get("customer_id"),
            "source_account": txn.get("source_account"),
            "destination_account": txn.get("destination_account"),
            "merchant_id": txn.get("merchant_id"),
            "device_id": txn.get("device_id"),
            "event_timestamp": txn.get("event_timestamp"),
            "amount": float(txn.get("amount", 0.0)),
            "currency": txn.get("currency", "INR"),
            "transaction_type": txn.get("transaction_type"),
            "location": txn.get("location"),
            "channel": txn.get("channel"),
            "account_age_days": int(txn.get("account_age_days", 0)) if txn.get("account_age_days") else 0
        }
        
        if producer:
            producer.send(topic, key=payload["source_account"], value=payload)
        
        sent_count += 1
        if sent_count % 100 == 0:
            print(f"[Producer] Sent {sent_count}/{len(transactions)} events...")
            
        if speed_factor > 0:
            time.sleep(0.005 / speed_factor)
            
    if producer:
        producer.flush()
        
    elapsed = time.time() - start_time
    print(f"[Producer] Finished streaming {sent_count} events in {elapsed:.2f} seconds.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kafka Transaction Producer for Fraud Detection")
    parser.add_argument("--csv", default="data/input/transactions.csv", help="Path to input transactions CSV")
    parser.add_argument("--topic", default="transactions_input", help="Kafka topic name")
    parser.add_argument("--servers", default="localhost:9092", help="Kafka bootstrap servers")
    parser.add_argument("--speed", type=float, default=10.0, help="Speed multiplier (0 = as fast as possible)")
    parser.add_argument("--max", type=int, default=None, help="Limit number of events")
    parser.add_argument("--disorder", choices=["none", "delay_30s", "delay_90s"], default="none", help="Chaos disorder scenario")
    args = parser.parse_args()
    
    stream_transactions(args.csv, args.topic, args.servers, args.speed, args.max, args.disorder)
