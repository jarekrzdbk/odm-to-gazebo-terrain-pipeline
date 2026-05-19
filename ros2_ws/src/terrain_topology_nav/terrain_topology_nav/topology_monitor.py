#!/usr/bin/env python3
import json, numpy as np, rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSHistoryPolicy, QoSReliabilityPolicy
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Float32, String
try:
    import gudhi as gd
except ImportError as exc:
    raise SystemExit("Missing gudhi. Install it first.") from exc

class TopologyMonitor(Node):
    def __init__(self):
        super().__init__("topology_monitor")
        self.declare_parameter("map_topic", "/map")
        qos = QoSProfile(history=QoSHistoryPolicy.KEEP_LAST, depth=1, reliability=QoSReliabilityPolicy.RELIABLE, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
        topic = self.get_parameter("map_topic").value
        self.sub = self.create_subscription(OccupancyGrid, topic, self.on_map, qos)
        self.pub_score = self.create_publisher(Float32, "/terrain/topology/corridor_stability", 10)
        self.pub_summary = self.create_publisher(String, "/terrain/topology/summary", 10)

    def on_map(self, msg: OccupancyGrid):
        w, h = msg.info.width, msg.info.height
        data = np.array(msg.data, dtype=np.int16).reshape((h, w))
        unknown = data < 0; occ = np.clip(data.astype(np.float32), 0.0, 100.0) / 100.0
        free_prob = 1.0 - occ; free_prob[unknown] = np.nan
        cost = np.nan_to_num(1.0 - free_prob, nan=1.0)
        cc = gd.CubicalComplex(top_dimensional_cells=cost.astype(np.float64)); diag = cc.persistence()
        h0, h1 = [], []
        for dim, (birth, death) in diag:
            length = 1.0 - float(birth) if np.isinf(death) else float(death - birth)
            if dim == 0: h0.append(length)
            elif dim == 1: h1.append(length)
        h0.sort(reverse=True); h1.sort(reverse=True)
        score_msg = Float32(); score_msg.data = float(h1[0]) if h1 else 0.0; self.pub_score.publish(score_msg)
        text = String(); text.data = json.dumps({"main_region_persistence": float(h0[0]) if h0 else 0.0, "corridor_stability_score": float(h1[0]) if h1 else 0.0, "top_h0_bars": h0[:5], "top_h1_bars": h1[:5], "width": int(w), "height": int(h), "resolution": float(msg.info.resolution)}); self.pub_summary.publish(text)

def main():
    rclpy.init(); node = TopologyMonitor()
    try: rclpy.spin(node)
    finally: node.destroy_node(); rclpy.shutdown()
