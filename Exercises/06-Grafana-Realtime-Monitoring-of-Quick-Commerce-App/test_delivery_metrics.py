import unittest

from prometheus_client import REGISTRY

import delivery_metrics as dm


class TestDeliveryMetrics(unittest.TestCase):
    def test_simulate_delivery_sets_all_metrics(self):
        count_before = REGISTRY.get_sample_value("average_delivery_time_count") or 0

        dm.simulate_delivery()

        pending = REGISTRY.get_sample_value("pending_deliveries")
        on_the_way = REGISTRY.get_sample_value("on_the_way_deliveries")
        total = REGISTRY.get_sample_value("total_deliveries")

        self.assertTrue(dm.PENDING_MIN <= pending <= dm.PENDING_MAX)
        self.assertTrue(5 <= on_the_way <= 20)
        self.assertGreaterEqual(total, pending + on_the_way + 30)
        self.assertEqual(REGISTRY.get_sample_value("average_delivery_time_count"), count_before + 1)

    def test_average_delivery_time_within_range(self):
        dm.simulate_delivery()
        total = REGISTRY.get_sample_value("average_delivery_time_sum")
        count = REGISTRY.get_sample_value("average_delivery_time_count")
        self.assertTrue(dm.DELIVERY_TIME_MIN <= total / count <= dm.DELIVERY_TIME_MAX)


if __name__ == "__main__":
    unittest.main()
