#!/usr/bin/env python3
import json, cv2, numpy as np, onnxruntime as ort, rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String

def default_palette():
    return np.array([[0,0,0],[180,180,180],[60,180,75],[230,25,75],[0,130,200],[245,130,48],[34,139,34],[255,225,25]], dtype=np.uint8)

class SemanticSegmentationNode(Node):
    def __init__(self):
        super().__init__("semantic_segmentation_node")
        self.bridge = CvBridge()
        self.declare_parameter("image_topic", "/camera/image_raw"); self.declare_parameter("model_path", ""); self.declare_parameter("input_size", 512)
        self.image_topic = self.get_parameter("image_topic").value; model_path = self.get_parameter("model_path").value; self.input_size = int(self.get_parameter("input_size").value)
        if not model_path: raise RuntimeError("Set parameter model_path to an ONNX segmentation model")
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"]); self.input_name = self.session.get_inputs()[0].name
        self.sub = self.create_subscription(Image, self.image_topic, self.on_image, 10)
        self.pub_labels = self.create_publisher(Image, "/semantic/labels", 10)
        self.pub_color = self.create_publisher(Image, "/semantic/color_mask", 10)
        self.pub_summary = self.create_publisher(String, "/semantic/summary", 10)
        self.palette = default_palette()

    def preprocess(self, rgb):
        img = cv2.resize(rgb, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)
        x = np.transpose(img.astype(np.float32) / 255.0, (2,0,1))[None, ...]
        return x

    def postprocess(self, outputs, out_h, out_w):
        pred = outputs[0]
        if pred.ndim == 4: labels = np.argmax(pred[0], axis=0).astype(np.uint8)
        elif pred.ndim == 3: labels = np.argmax(pred, axis=0).astype(np.uint8)
        else: raise RuntimeError(f"Unsupported segmentation output shape: {pred.shape}")
        return cv2.resize(labels, (out_w, out_h), interpolation=cv2.INTER_NEAREST)

    def on_image(self, msg):
        rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding="rgb8"); h, w = rgb.shape[:2]
        outputs = self.session.run(None, {self.input_name: self.preprocess(rgb)}); labels = self.postprocess(outputs, h, w)
        color = self.palette[np.clip(labels, 0, len(self.palette)-1)]
        label_msg = self.bridge.cv2_to_imgmsg(labels, encoding="mono8"); label_msg.header = msg.header
        color_msg = self.bridge.cv2_to_imgmsg(color, encoding="rgb8"); color_msg.header = msg.header
        self.pub_labels.publish(label_msg); self.pub_color.publish(color_msg)
        uniques, counts = np.unique(labels, return_counts=True); text = String(); text.data = json.dumps({"classes": {int(k): int(v) for k, v in zip(uniques, counts)}}); self.pub_summary.publish(text)

def main():
    rclpy.init(); node = SemanticSegmentationNode()
    try: rclpy.spin(node)
    finally: node.destroy_node(); rclpy.shutdown()
