# save as voxel_carving.py and run with: python voxel_carving.py
import numpy as np
import cv2
from skimage import measure
import trimesh
import matplotlib.pyplot as plt
import sys

# ---------- USER CONFIG ----------
front_path = "front_mask.png"   # binary silhouette (255 = foreground)
side_path  = "side_mask.png"
top_path   = "top_mask.png"

# voxel grid resolution (increase for finer detail; costs memory/time)
VOX_RES = 200  # try 100..300 depending on memory (200 is moderate)

# bounding box in world coords (units arbitrary). We'll assume x = left-right, y = front-back, z = height
# We align the 3 images to this box: front view sees x horizontally, z vertically
# side  view sees y horizontally, z vertically
# top   view sees x horizontally, y vertically
X_MIN, X_MAX = -0.5, 0.5
Y_MIN, Y_MAX = -0.5, 0.5
Z_MIN, Z_MAX = 0.0, 1.8
# ----------------------------------

def load_mask(path):
    m = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if m is None:
        print("Cannot load", path); sys.exit(1)
    # threshold to binary
    _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
    return (m > 0).astype(np.uint8)

front_mask = load_mask(front_path)
side_mask  = load_mask(side_path)
top_mask   = load_mask(top_path)

h_f, w_f = front_mask.shape
h_s, w_s = side_mask.shape
h_t, w_t = top_mask.shape

# Create voxel grid coordinates
xs = np.linspace(X_MIN, X_MAX, VOX_RES)
ys = np.linspace(Y_MIN, Y_MAX, VOX_RES)
zs = np.linspace(Z_MIN, Z_MAX, VOX_RES)
Xg, Yg, Zg = np.meshgrid(xs, ys, zs, indexing='xy')  # shape (VOX_RES, VOX_RES, VOX_RES)

# Flatten for vectorized processing
pts = np.vstack((Xg.ravel(), Yg.ravel(), Zg.ravel())).T  # (N,3)

# Projection functions for orthographic views -> image pixel coordinates
def project_front(pt):
    # front: x -> col, z -> row
    x, y, z = pt
    col_f = ( (x - X_MIN) / (X_MAX - X_MIN) ) * (w_f-1)
    row_f = ( 1 - (z - Z_MIN) / (Z_MAX - Z_MIN) ) * (h_f-1)  # z up -> row decreases
    return int(round(row_f)), int(round(col_f))

def project_side(pt):
    # side: y -> col, z -> row (assume viewer at +x looking at -x side)
    x, y, z = pt
    col_s = ( (y - Y_MIN) / (Y_MAX - Y_MIN) ) * (w_s-1)
    row_s = ( 1 - (z - Z_MIN) / (Z_MAX - Z_MIN) ) * (h_s-1)
    return int(round(row_s)), int(round(col_s))

def project_top(pt):
    # top: x -> col, y -> row (top-down; z ignored)
    x, y, z = pt
    col_t = ( (x - X_MIN) / (X_MAX - X_MIN) ) * (w_t-1)
    row_t = ( 1 - ( (y - Y_MIN) / (Y_MAX - Y_MIN) ) ) * (h_t-1)  # invert so +y→top->row small
    return int(round(row_t)), int(round(col_t))

# For memory, process in chunks
N = pts.shape[0]
keep = np.ones(N, dtype=bool)

chunk = 2000000  # process ~2M voxels per chunk. adjust if memory issues
for i in range(0, N, chunk):
    j = min(i+chunk, N)
    P = pts[i:j]
    # project all
    rf = np.clip(((1 - (P[:,2]-Z_MIN)/(Z_MAX-Z_MIN))*(h_f-1)).round().astype(int), 0, h_f-1)
    cf = np.clip((((P[:,0]-X_MIN)/(X_MAX-X_MIN))*(w_f-1)).round().astype(int), 0, w_f-1)
    rs = np.clip(((1 - (P[:,2]-Z_MIN)/(Z_MAX-Z_MIN))*(h_s-1)).round().astype(int), 0, h_s-1)
    cs = np.clip((((P[:,1]-Y_MIN)/(Y_MAX-Y_MIN))*(w_s-1)).round().astype(int), 0, w_s-1)
    rt = np.clip(((1 - ((P[:,1]-Y_MIN)/(Y_MAX-Y_MIN)))*(h_t-1)).round().astype(int), 0, h_t-1)
    ct = np.clip((((P[:,0]-X_MIN)/(X_MAX-X_MIN))*(w_t-1)).round().astype(int), 0, w_t-1)

    inside_all = (front_mask[rf, cf] > 0) & (side_mask[rs, cs] > 0) & (top_mask[rt, ct] > 0)
    keep[i:j] = inside_all

# Reshape to voxel volume
vol = keep.reshape((VOX_RES, VOX_RES, VOX_RES)).astype(np.uint8)  # dims: x,y,z

# We want a 3D array suitable for marching cubes: shape (nx,ny,nz)
# marching_cubes expects array with axis order (z,y,x) sometimes — we'll transpose to (z,y,x)
vol_for_mc = np.transpose(vol, (2,1,0))  # now axes are z,y,x

# Extract surface via marching cubes
verts, faces, normals, _ = measure.marching_cubes(vol_for_mc, level=0.5, spacing=( (Z_MAX-Z_MIN)/(VOX_RES-1),
                                                                                  (Y_MAX-Y_MIN)/(VOX_RES-1),
                                                                                  (X_MAX-X_MIN)/(VOX_RES-1)))
# marching_cubes returned verts in order (z, y, x) spacing matched. Convert vertices to (x,y,z) in world coords:
verts_xyz = np.vstack([verts[:,2] + X_MIN/(X_MAX-X_MIN), verts[:,1] + Y_MIN/(Y_MAX-Y_MIN), verts[:,0] + Z_MIN/(Z_MAX-Z_MIN)]).T
# The above conversion is a simplistic mapping; better compute actual coordinates:
# compute better:
verts_xyz = np.zeros_like(verts)
verts_xyz[:,0] = verts[:,2] * (X_MAX - X_MIN) / (VOX_RES-1) + X_MIN
verts_xyz[:,1] = verts[:,1] * (Y_MAX - Y_MIN) / (VOX_RES-1) + Y_MIN
verts_xyz[:,2] = verts[:,0] * (Z_MAX - Z_MIN) / (VOX_RES-1) + Z_MIN

mesh = trimesh.Trimesh(vertices=verts_xyz, faces=faces, vertex_normals=normals)
mesh.export("result.ply")
print("Saved result.ply — open in MeshLab/Blender. Voxel count:", vol.sum())
