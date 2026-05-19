#!/usr/bin/env python3
import json
from dataclasses import dataclass
import cv2, numpy as np, onnxruntime as ort, rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String

@dataclass
class Track:
    track_id: int
    box: np.ndarray
    cls: int
    score: float
    age: int = 0

def iou(a, b):
    ax1, ay1, ax2, ay2 = a; bx1, by1, bx2, by2 = b
    ix1, iy1, ix2, iy2 = max(ax1,bx1), max(ay1,by1), min(ax2,bx2), min(ay2,by2)
    iw, ih = max(0.0, ix2-ix1), max(0.0, iy2-iy1)
    inter = iw * ih; area_a = max(0.0, ax2-ax1) * max(0.0, ay2-ay1); area_b = max(0.0, bx2-bx1) * max(0.0, by2-by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0

class DetectorTrackerNode(Node):
    def __init__(self):
        super().__init__("object_detector_tracker")
        self.bridge = CvBridge()
        for name, default in [("image_topic","/camera/image_raw"),("model_path",""),("input_size",640),("score_threshold",0.35),("iou_threshold",0.4),("max_age",10)]:
            self.declare_parameter(name, default)
        model_path = self.get_parameter("model_path").value
        if not model_path: raise RuntimeError("Set parameter model_path to an ONNX detector")
        self.image_topic = self.get_parameter("image_topic").value; self.input_size = int(self.get_parameter("input_size").value); self.score_threshold = float(self.get_parameter("score_threshold").value); self.iou_threshold = float(self.get_parameter("iou_threshold").value); self.max_age = int(self.get_parameter("max_age").value)
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"]); self.input_name = self.session.get_inputs()[0].name
        self.tracks = []; self.next_track_id = 1
        self.sub = self.create_subscription(Image, self.image_topic, self.on_image, 10)
        self.pub_annotated = self.create_publisher(Image, "/perception/detections_annotated", 10)
        self.pub_tracks = self.create_publisher(String, "/perception/tracks", 10)

    def preprocess(self, rgb):
        img = cv2.resize(rgb, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)
        return np.transpose(img.astype(np.float32) / 255.0, (2,0,1))[None, ...]

    def parse_detections(self, outputs, orig_w, orig_h):
        out = outputs[0]; dets = []
        if out.ndim == 2 and out.shape[1] >= 6:
            rows = out
            for row in rows:
                score = float(row[4]); 
                if score < self.score_threshold: continue
                x1, y1, x2, y2 = row[:4]; cls = int(row[5]); dets.append([float(x1), float(y1), float(x2), float(y2), score, cls])
        elif out.ndim == 3 and out.shape[0] == 1 and out.shape[2] >= 6:
            rows = out[0]
            for row in rows:
                if out.shape[2] == 7 and row[2] <= 1.0:
                    score = float(row[2]); 
                    if score < self.score_threshold: continue
                    cls = int(row[1]); x1, y1, x2, y2 = row[3:7]
                else:
                    score = float(row[4]); 
                    if score < self.score_threshold: continue
                    x1, y1, x2, y2 = row[:4]; cls = int(row[5])
                dets.append([float(x1), float(y1), float(x2), float(y2), score, cls])
        else:
            raise RuntimeError(f"Unsupported detector output shape: {out.shape}")
        sx, sy = orig_w / self.input_size, orig_h / self.input_size
        return [np.array([x1*sx, y1*sy, x2*sx, y2*sy, score, cls], dtype=np.float32) for x1,y1,x2,y2,score,cls in dets]

    def update_tracks(self, dets):
        for tr in self.tracks: tr.age += 1
        for det in dets:
            box, score, cls = det[:4], float(det[4]), int(det[5]); best_idx = None; best_i = 0.0
            for idx, tr in enumerate(self.tracks):
                if tr.cls != cls: continue
                ov = iou(tr.box, box)
                if ov > best_i: best_i, best_idx = ov, idx
            if best_idx is not None and best_i >= self.iou_threshold:
                tr = self.tracks[best_idx]; tr.box = box; tr.score = score; tr.age = 0
            else:
                self.tracks.append(Track(self.next_track_id, box, cls, score, age=0)); self.next_track_id += 1
        self.tracks = [tr for tr in self.tracks if tr.age <= self.max_age]

    def on_image(self, msg):
        rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding="rgb8"); h, w = rgb.shape[:2]
        dets = self.parse_detections(self.session.run(None, {self.input_name: self.preprocess(rgb)}), w, h); self.update_tracks(dets)
        vis = rgb.copy(); payload = {"tracks": []}
        for tr in self.tracks:
            x1,y1,x2,y2 = tr.box.astype(int)
            cv2.rectangle(vis, (x1,y1), (x2,y2), (0,255,0), 2); cv2.putText(vis, f"id={tr.track_id} cls={tr.cls} s={tr.score:.2f}", (x1, max(0,y1-6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1, cv2.LINE_AA)
            payload["tracks"].append({"track_id": tr.track_id, "class_id": tr.cls, "score": float(tr.score), "box_xyxy": [float(v) for v in tr.box]})
        out_msg = self.bridge.cv2_to_imgmsg(vis, encoding="rgb8"); out_msg.header = msg.header; self.pub_annotated.publish(out_msg)
        text = String(); text.data = json.dumps(payload); self.pub_tracks.publish(text)

def main():
    rclpy.init(); node = DetectorTrackerNode()
    try: rclpy.spin(node)
    finally: node.destroy_node(); rclpy.shutdown()
