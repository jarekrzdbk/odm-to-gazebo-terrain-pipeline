#!/usr/bin/env python3
import argparse
from pathlib import Path
from textwrap import dedent


def parse_obj_vertices(path: Path):
    vertices = []

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    x, y, z = map(float, parts[1:4])
                    vertices.append((x, y, z))

    if not vertices:
        raise ValueError(f"No vertices found in OBJ: {path}")

    return vertices


def compute_bounds(vertices):
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]

    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
        "min_z": min(zs),
        "max_z": max(zs),
    }


def estimate_center_z(vertices, center_x, center_y):
    best = None
    best_d2 = None

    for x, y, z in vertices:
        d2 = (x - center_x) ** 2 + (y - center_y) ** 2
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best = (x, y, z)

    if best is None:
        raise ValueError("Could not estimate center terrain height")

    return best[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--xy-scale", type=float, default=1.0)
    ap.add_argument("--z-scale", type=float, default=1.0)
    ap.add_argument("--add-mesh", type=int, default=1)
    ap.add_argument("--mesh-x-offset", type=float, default=0.0)
    ap.add_argument("--mesh-y-offset", type=float, default=0.0)
    ap.add_argument("--mesh-z-offset", type=float, default=None)
    ap.add_argument("--mesh-z-delta", type=float, default=0.0)
    ap.add_argument(
        "--z-origin-mode",
        choices=["ground", "center"],
        default="center",
        help="ground: lowest point at z=0; center: mesh vertically centered around z=0",
    )
    args = ap.parse_args()

    dataset = Path(args.dataset).resolve()
    repo_root = Path(args.repo_root).resolve()
    template_path = Path(args.template).resolve()
    output_path = Path(args.output).resolve()

    mesh_candidates = [
        dataset / "odm_texturing_25d" / "odm_textured_model_geo.obj",
        dataset / "odm_texturing_25d" / "odm_textured_model.obj",
        dataset / "odm_texturing" / "odm_textured_model_geo.obj",
        dataset / "odm_texturing" / "odm_textured_model.obj",
    ]
    mesh_obj = next((p for p in mesh_candidates if p.exists()), None)

    if mesh_obj is None:
        raise FileNotFoundError(
            "Could not find a textured OBJ mesh in odm_texturing or odm_texturing_25d"
        )

    vertices = parse_obj_vertices(mesh_obj)
    bounds = compute_bounds(vertices)

    min_x = bounds["min_x"]
    max_x = bounds["max_x"]
    min_y = bounds["min_y"]
    max_y = bounds["max_y"]
    min_z = bounds["min_z"]
    max_z = bounds["max_z"]

    center_x = 0.5 * (min_x + max_x)
    center_y = 0.5 * (min_y + max_y)
    center_z = 0.5 * (min_z + max_z)

    width = (max_x - min_x) * args.xy_scale
    height = (max_y - min_y) * args.xy_scale
    z_range = (max_z - min_z) * args.z_scale

    auto_x = -center_x * args.xy_scale
    auto_y = -center_y * args.xy_scale

    if args.z_origin_mode == "ground":
        auto_z = -min_z * args.z_scale
    else:
        auto_z = -center_z * args.z_scale

    mesh_x = auto_x + args.mesh_x_offset
    mesh_y = auto_y + args.mesh_y_offset

    if args.mesh_z_offset is None:
        mesh_z = auto_z
    else:
        mesh_z = args.mesh_z_offset

    mesh_z += args.mesh_z_delta

    center_surface_z = estimate_center_z(vertices, center_x, center_y) * args.z_scale + mesh_z
    suggested_robot_z = center_surface_z + 1.0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    marker_block = dedent(
        """\
        <model name="origin_marker">
          <static>true</static>
          <pose>0 0 0.1 0 0 0</pose>
          <link name="marker_link">
            <visual name="marker_visual">
              <geometry>
                <box>
                  <size>2 2 0.2</size>
                </box>
              </geometry>
              <material>
                <ambient>1 0 0 1</ambient>
                <diffuse>1 0 0 1</diffuse>
              </material>
            </visual>
          </link>
        </model>
        """
    ).strip()

    mesh_block = ""
    if args.add_mesh:
        mesh_block = dedent(
            f"""\
            <model name="terrain_mesh">
              <static>true</static>
              <pose>{mesh_x:.6f} {mesh_y:.6f} {mesh_z:.6f} 0 0 0</pose>
              <link name="terrain_link">
                <collision name="terrain_collision">
                  <geometry>
                    <mesh>
                      <uri>file://{mesh_obj}</uri>
                      <scale>{args.xy_scale:.6f} {args.xy_scale:.6f} {args.z_scale:.6f}</scale>
                    </mesh>
                  </geometry>
                </collision>
                <visual name="terrain_visual">
                  <cast_shadows>false</cast_shadows>
                  <geometry>
                    <mesh>
                      <uri>file://{mesh_obj}</uri>
                      <scale>{args.xy_scale:.6f} {args.xy_scale:.6f} {args.z_scale:.6f}</scale>
                    </mesh>
                  </geometry>
                </visual>
              </link>
            </model>
            """
        ).strip()

    template = template_path.read_text(encoding="utf-8")
    sdf = template.format(
        marker_block=marker_block,
        mesh_block=mesh_block,
    )

    tmp_output = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_output.write_text(sdf, encoding="utf-8")
    tmp_output.replace(output_path)

    print(f"Wrote {output_path}")
    print(f"Using mesh: {mesh_obj}")
    print("Mesh bounds:")
    print(f"  x: {min_x:.3f} .. {max_x:.3f}")
    print(f"  y: {min_y:.3f} .. {max_y:.3f}")
    print(f"  z: {min_z:.3f} .. {max_z:.3f}")
    print(f"Approx world size: {width:.3f} x {height:.3f} x {z_range:.3f}")
    print(f"Z origin mode: {args.z_origin_mode}")
    print(f"Mesh pose: x={mesh_x:.3f} y={mesh_y:.3f} z={mesh_z:.3f}")
    print(f"Suggested ROBOT_Z near origin: {suggested_robot_z:.3f}")
    print("Set GZ_SIM_RESOURCE_PATH to include:")
    print(f"  {repo_root / 'gazebo' / 'models'}")


if __name__ == "__main__":
    main()
