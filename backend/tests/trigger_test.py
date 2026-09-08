import json
import time
from kafka import KafkaProducer


def inject_mock_attack():
    print("📡 [TEST HARNESS] Initializing Kafka telemetry injector...")

    # Connect directly to your externally exposed Kafka port
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    # ⚡ Simulated Target Details (Using a valid UUID footprint format)
    target_tenant = "00000000-0000-0000-0000-000000000000"
    attacker_ip = "203.0.113.50"


    print(f"🔥 Injecting 5 rapid authentication failures for IP: {attacker_ip}...")

    for i in range(5):
        payload = {
            "action": "user.login_failed",
            "tenant_id": target_tenant,
            "source_ip": attacker_ip,
            "timestamp": time.time()
        }
        # Send the payload straight into your active ingestion topic
        producer.send('security.events', value=payload)
        print(f"   [Sent Event {i + 1}/5] Log entry queued into Kafka.")
        time.sleep(0.2)  # Rapid injection mimicking a machine-driven brute force attack

    producer.flush()
    print("✅ [TEST HARNESS] Injection stream closed successfully.")


if __name__ == "__main__":
    inject_mock_attack()
