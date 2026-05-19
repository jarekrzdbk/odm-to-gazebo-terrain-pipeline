#!/usr/bin/env python3
import argparse
import json
import shutil
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


def find_mesh_obj(dataset: Path) -> Path:
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
    return mesh_obj


def load_terrain_meta(dataset: Path):
    meta_path = dataset / "terrain" / "terrain_meta.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def write_textured_plane(world_dir: Path, texture_path: Path, width: float, height: float, name: str):
    plane_dir = world_dir / f"{name}_assets"
    plane_dir.mkdir(parents=True, exist_ok=True)

    tex_dst = plane_dir / texture_path.name
    if texture_path.resolve() != tex_dst.resolve():
        shutil.copy2(texture_path, tex_dst)

    mtl_path = plane_dir / f"{name}.mtl"
    obj_path = plane_dir / f"{name}.obj"

    mtl = dedent(
        f"""\
        newmtl {name}_mat
        Ka 1.000 1.000 1.000
        Kd 1.000 1.000 1.000
        Ks 0.000 0.000 0.000
        d 1.0
        illum 1
        map_Kd {tex_dst.name}
        """
    )
    mtl_path.write_text(mtl, encoding="utf-8")

    hw = width / 2.0
    hh = height / 2.0

    obj = dedent(
        f"""\
        mtllib {mtl_path.name}
        o {name}
        v {-hw:.6f} {-hh:.6f} 0.000000
        v { hw:.6f} {-hh:.6f} 0.000000
        v { hw:.6f} { hh:.6f} 0.000000
        v {-hw:.6f} { hh:.6f} 0.000000
        vt 0.000000 0.000000
        vt 1.000000 0.000000
        vt 1.000000 1.000000
        vt 0.000000 1.000000
        vn 0.000000 0.000000 1.000000
        usemtl {name}_mat
        f 1/1/1 2/2/1 3/3/1
        f 1/1/1 3/3/1 4/4/1
        """
    )
    obj_path.write_text(obj, encoding="utf-8")

    return obj_path


def load_template(template_path: Path) -> str:
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--world-name", default="ortho_world")
    ap.add_argument("--xy-scale", type=float, default=1.0)
    ap.add_argument("--z-scale", type=float, default=1.0)
    ap.add_argument("--add-mesh", type=int, default=1)
    ap.add_argument("--world-file", default="generated_world.sdf")
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
    ap.add_argument(
        "--visual-mode",
        choices=["rgb", "semantic", "both"],
        default="rgb",
    )
    ap.add_argument(
        "--semantic-plane-image",
        default=None,
        help="Path to semantic blend PNG to show as a flat overlay plane.",
    )
    ap.add_argument(
        "--semantic-overlay-z",
        type=float,
        default=0.5,
        help="Extra height above mesh max_z for the semantic plane.",
    )
    args = ap.parse_args()

    dataset = Path(args.dataset).resolve()
    repo_root = Path(args.repo_root).resolve()
    template_path = Path(args.template).resolve()

    world_dir = dataset / "gazebo_world"
    world_dir.mkdir(parents=True, exist_ok=True)
    world_path = world_dir / args.world_file

    mesh_obj = find_mesh_obj(dataset)
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

    terrain_meta = load_terrain_meta(dataset)
    if terrain_meta:
        plane_width = float(terrain_meta.get("world_width", width))
        plane_height = float(terrain_meta.get("world_height", height))
    else:
        plane_width = width
        plane_height = height

    semantic_plane_block = ""
    if args.visual_mode in ("semantic", "both"):
        if not args.semantic_plane_image:
            raise ValueError("visual-mode semantic/both requires --semantic-plane-image")

        plane_tex = Path(args.semantic_plane_image).resolve()
        if not plane_tex.exists():
            raise FileNotFoundError(f"Semantic plane image not found: {plane_tex}")

        plane_obj = write_textured_plane(
            world_dir=world_dir,
            texture_path=plane_tex,
            width=plane_width,
            height=plane_height,
            name="semantic_plane",
        )

        plane_z = mesh_z + (max_z * args.z_scale) + args.semantic_overlay_z

        semantic_plane_block = f"""
    <model name="terrain_mesh_semantic_overlay">
      <static>true</static>
      <pose>0 0 {plane_z:.6f} 0 0 0</pose>
      <link name="terrain_mesh_semantic_overlay_link">
        <visual name="terrain_mesh_semantic_overlay_visual">
          <cast_shadows>false</cast_shadows>
          <transparency>0.15</transparency>
          <geometry>
            <mesh>
              <uri>file://{plane_obj}</uri>
              <scale>1 1 1</scale>
            </mesh>
          </geometry>
        </visual>
      </link>
    </model>
"""

    marker_block = """
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

    mesh_block = ""
    if args.add_mesh:
        mesh_block = f"""
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

    if args.visual_mode == "semantic":
        mesh_block = ""

    template = load_template(template_path)
    sdf = template.format(
        world_name=args.world_name,
        marker_block=marker_block.strip("\n"),
        mesh_block=mesh_block.strip("\n"),
        semantic_plane_block=semantic_plane_block.strip("\n"),
    )

    world_path.write_text(dedent(sdf), encoding="utf-8")

    print(f"Wrote {world_path}")
    print(f"Using template: {template_path}")
    print(f"Using mesh: {mesh_obj}")
    print("Mesh bounds:")
    print(f"  x: {min_x:.3f} .. {max_x:.3f}")
    print(f"  y: {min_y:.3f} .. {max_y:.3f}")
    print(f"  z: {min_z:.3f} .. {max_z:.3f}")
    print(f"Approx world size: {width:.3f} x {height:.3f} x {z_range:.3f}")
    print(f"Z origin mode: {args.z_origin_mode}")
    print(f"Mesh pose: x={mesh_x:.3f} y={mesh_y:.3f} z={mesh_z:.3f}")
    print(f"Suggested ROBOT_Z near origin: {suggested_robot_z:.3f}")
    print(f"Set GZ_SIM_RESOURCE_PATH to include: {repo_root / 'gazebo' / 'models'}")


if __name__ == "__main__":
    main()
