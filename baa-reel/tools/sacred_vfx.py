"""Sovereign 30 FPS Calligraphic, Sacred-Geometric & Particle VFX Engine.

Implements the three visual identities of the Master Production Prompt:
  1. الهوية الأولى: المخطوطات السيادية (Chiaroscuro vellum, antique gold leaf, deep shadows)
  2. الهوية الثانية: سر النقطة (Vector-separated «ب» & incandescent Nuqta core)
  3. الهوية الثالثة: الهندسة الكونية (Animated Islamic geometry, particle condensation, light waves,
     3D sacred polyhedra, and the Seven-Secrets Key emblem of the Academy)
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

import artext

W, H = 1080, 1920
OVERSCAN_W, OVERSCAN_H = 1296, 2304


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


# --------------------------------------------------------------------------- #
# 1. Clean Chiaroscuro Plate Preparation & Retouching
# --------------------------------------------------------------------------- #
def retouch_raw_plate(name: str, img: Image.Image) -> Image.Image:
    """Ensure 100% pure Arabo-Islamic heritage plates free of stray marks or figures."""
    arr = np.asarray(img.convert("RGB"), dtype=np.float32).copy()
    h, w, _ = arr.shape

    if name == "s02_fourfold_square":
        # Cleanly replace tiny pseudo-glyph ticks inside the brass square with smooth bronze-parchment grain
        boxes = [
            (0.382, 0.458, 0.285, 0.405, -0.145, -0.120),
            (0.382, 0.458, 0.595, 0.715, -0.145, +0.100),
            (0.548, 0.628, 0.285, 0.405, +0.145, -0.120),
            (0.548, 0.628, 0.595, 0.715, +0.145, +0.100),
        ]
        blur_ref = np.asarray(
            Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(9)),
            dtype=np.float32,
        )
        for y0f, y1f, x0f, x1f, dyf, dxf in boxes:
            y0, y1 = int(y0f * h), int(y1f * h)
            x0, x1 = int(x0f * w), int(x1f * w)
            patch = blur_ref[y0:y1, x0:x1] * 0.72 + np.array([28.0, 19.0, 11.0]) * 0.28
            yy = np.sin(np.linspace(0, math.pi, y1 - y0))[:, None, None]
            xx = np.sin(np.linspace(0, math.pi, x1 - x0))[None, :, None]
            m = np.clip((yy * xx) ** 0.55 * 1.15, 0, 1)
            arr[y0:y1, x0:x1] = arr[y0:y1, x0:x1] * (1 - m) + patch * m

    elif name == "s04_alchemical_mizan":
        # Completely replace right-background silhouette with deep charcoal stone shadow (above scale pan)
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
        rx = np.clip((xx - 0.56) / 0.13, 0.0, 1.0)
        # Keep right balance pan (yy > 0.745) untouched; dissolve 0.34..0.745 into pure charcoal wall shadow
        ry_top = np.clip((yy - 0.30) / 0.10, 0.0, 1.0)
        ry_bot = np.clip((0.752 - yy) / 0.055, 0.0, 1.0)
        mask = (rx * ry_top * ry_bot)[..., None]
        rng = np.random.default_rng(19)
        grain = rng.normal(0.0, 1.8, (h, w, 1)).astype(np.float32)
        dark_wall = np.clip(np.array([11.0, 9.5, 11.5]) + grain, 4.0, 22.0)
        arr = arr * (1.0 - mask) + dark_wall * mask

    elif name == "s06_sovereign_manuscript":
        # Cast deep Chiaroscuro column shadow on far-left & far-right walls to keep pure Islamic sanctuary feel
        xx = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        side_shadow = np.clip((0.20 - xx) / 0.16, 0.0, 1.0) + np.clip((xx - 0.82) / 0.16, 0.0, 1.0)
        top_arch = np.clip((0.12 - yy) / 0.12, 0.0, 1.0) * 0.5
        s_mask = np.clip(side_shadow + top_arch, 0.0, 0.92)
        arr = arr * (1.0 - s_mask) + np.array([9.0, 8.0, 11.0]) * s_mask

    # Unified Sovereign Chiaroscuro Cinema Grade (charcoal shadows + warm antique gold highlights)
    lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0
    # Crush milky blacks slightly for rich OLED charcoal look
    crush = np.clip((lum - 0.03) / 0.97, 0.0, 1.0) ** 1.08
    scale = (crush / (lum + 1e-5))[..., None]
    arr = np.clip(arr * scale, 0, 255)
    # Warm golden-bronze tint in midtones/highlights, cool-charcoal in deepest shadows
    hi = (lum ** 1.3)[..., None]
    arr[..., 0] = np.clip(arr[..., 0] * 1.04 + hi[..., 0] * 7.0, 0, 255)
    arr[..., 1] = np.clip(arr[..., 1] * 0.99 + hi[..., 0] * 2.5, 0, 255)
    arr[..., 2] = np.clip(arr[..., 2] * 0.91 - hi[..., 0] * 4.0, 0, 255)

    out = Image.fromarray(arr.astype(np.uint8), mode="RGB")
    # Center-crop/scale cleanly to 9:16 overscan (1296x2304) without aspect distortion
    target_ratio = OVERSCAN_W / OVERSCAN_H
    src_ratio = out.width / out.height
    if src_ratio > target_ratio:
        nw = int(round(out.height * target_ratio))
        x0 = (out.width - nw) // 2
        out = out.crop((x0, 0, x0 + nw, out.height))
    elif src_ratio < target_ratio:
        nh = int(round(out.width / target_ratio))
        y0 = (out.height - nh) // 2
        out = out.crop((0, y0, out.width, y0 + nh))
    return out.resize((OVERSCAN_W, OVERSCAN_H), Image.LANCZOS)


# --------------------------------------------------------------------------- #
# 2. Vector Calligraphic «ب» & Incandescent Nuqta Renderer
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=6)
def _cached_baa_masks(font_path: str, size: int):
    anat = artext.extract_baa_anatomy(font_path, size)
    cw, ch = anat["width"], anat["height"]
    ss = 2

    v_mask = Image.new("L", (cw * ss, ch * ss), 0)
    vd = ImageDraw.Draw(v_mask)
    for c in anat["vessel"]:
        vd.polygon([(p[0] * ss, p[1] * ss) for p in c], fill=255)
    v_mask = v_mask.resize((cw, ch), Image.LANCZOS)

    n_mask = Image.new("L", (cw * ss, ch * ss), 0)
    nd = ImageDraw.Draw(n_mask)
    for c in anat["nuqta"]:
        nd.polygon([(p[0] * ss, p[1] * ss) for p in c], fill=255)
    n_mask = n_mask.resize((cw, ch), Image.LANCZOS)

    return anat, v_mask, n_mask


def draw_nuqta_energy(
    canvas: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    intensity: float = 1.0,
    rays: int = 12,
    rot: float = 0.0,
):
    """Render volumetric golden singularity glow + subtle rays around the Nuqta (fast local patch)."""
    if intensity <= 0.01 or radius <= 1.0:
        return
    half = int(min(720, max(96, radius * 3.2)))
    psize = half * 2
    # Render at half-res for ultra-fast smooth volumetric Gaussian bloom
    hs = max(32, half)
    patch = Image.new("RGBA", (hs * 2, hs * 2), (0, 0, 0, 0))
    pcx = pcy = float(hs)
    r_half = radius * 0.5

    if rays > 0 and intensity > 0.15:
        ray_layer = Image.new("RGBA", patch.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(ray_layer)
        for i in range(rays):
            ang = rot + i * (2 * math.pi / rays)
            length = r_half * (2.6 if i % 2 == 0 else 1.65)
            spread = 0.055 if i % 2 == 0 else 0.035
            p1 = (pcx + math.cos(ang - spread) * r_half * 0.2, pcy + math.sin(ang - spread) * r_half * 0.2)
            p2 = (pcx + math.cos(ang) * length, pcy + math.sin(ang) * length)
            p3 = (pcx + math.cos(ang + spread) * r_half * 0.2, pcy + math.sin(ang + spread) * r_half * 0.2)
            alpha = int(min(130, 58 * intensity * (1.0 if i % 2 == 0 else 0.65)))
            rd.polygon([p1, p2, p3], fill=(244, 202, 112, alpha))
        ray_layer = ray_layer.filter(ImageFilter.GaussianBlur(max(2, int(r_half * 0.14))))
        patch = Image.alpha_composite(patch, ray_layer)

    glow = Image.new("RGBA", patch.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for mult, col, a_scale in [
        (2.0, (196, 138, 52), 0.28),
        (1.12, (238, 192, 98), 0.52),
        (0.52, (255, 244, 206), 0.85),
        (0.22, (255, 253, 246), 0.98),
    ]:
        r = max(1.5, r_half * mult)
        alpha = int(min(255, 255 * a_scale * intensity))
        gd.ellipse([pcx - r, pcy - r, pcx + r, pcy + r], fill=(*col, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(max(4, int(r_half * 0.52))))
    patch = Image.alpha_composite(patch, glow).resize((psize, psize), Image.BILINEAR)

    ox, oy = int(round(cx - half)), int(round(cy - half))
    # Clip cleanly if patch extends outside canvas bounds
    sx0 = max(0, -ox)
    sy0 = max(0, -oy)
    dx0 = max(0, ox)
    dy0 = max(0, oy)
    w_avail = min(psize - sx0, canvas.width - dx0)
    h_avail = min(psize - sy0, canvas.height - dy0)
    if w_avail > 0 and h_avail > 0:
        sub = patch.crop((sx0, sy0, sx0 + w_avail, sy0 + h_avail))
        canvas.alpha_composite(sub, (dx0, dy0))


@lru_cache(maxsize=96)
def _cached_gold_part(font_path: str, size: int, is_nuqta: bool, sheen_step: int) -> Image.Image:
    anat, v_mask, n_mask = _cached_baa_masks(font_path, size)
    mask = n_mask if is_nuqta else v_mask
    glow_r = 14 if is_nuqta else 16
    bev = 1.1 if is_nuqta else 1.25
    return artext.apply_gold_leaf(mask, sheen_pos=sheen_step / 40.0, glow_radius=glow_r, bevel=bev)


def render_hero_baa(
    canvas: Image.Image,
    font_path: str,
    center_xy: tuple[float, float],
    size: int = 520,
    vessel_reveal: float = 1.0,
    nuqta_scale: float = 1.0,
    nuqta_glow: float = 1.0,
    sheen_pos: float = 0.5,
    opacity: float = 1.0,
    rot_rays: float = 0.0,
) -> tuple[float, float]:
    """Composite embossed gold-leaf «ب» onto `canvas` and return world Nuqta (nx, ny)."""
    anat, v_mask, n_mask = _cached_baa_masks(font_path, size)
    cw, ch = anat["width"], anat["height"]
    vx0, vy0, vx1, vy1 = anat["vessel_bbox"]
    ncx, ncy = anat["nuqta_center"]
    s_step = max(0, min(48, int(round((sheen_pos % 1.2) * 40))))

    ox = int(round(center_xy[0] - cw / 2))
    oy = int(round(center_xy[1] - ch / 2))
    world_nx = ox + ncx
    world_ny = oy + ncy

    # 1. Nuqta volumetric aura behind glyph
    if nuqta_glow > 0.02:
        draw_nuqta_energy(
            canvas,
            world_nx,
            world_ny,
            radius=size * 0.26 * max(0.5, nuqta_glow),
            intensity=min(1.3, nuqta_glow * opacity),
            rays=12,
            rot=rot_rays,
        )

    # 2. Vessel right-to-left progressive calligraphic reveal
    if vessel_reveal > 0.005:
        if vessel_reveal < 0.999:
            arr = np.asarray(v_mask, dtype=np.float32)
            xs = np.linspace(0, cw - 1, cw, dtype=np.float32)[None, :]
            cutoff = vx1 - (vx1 - vx0) * vessel_reveal
            feather = max(8.0, (vx1 - vx0) * 0.07)
            gate = np.clip((xs - (cutoff - feather)) / feather, 0.0, 1.0)
            vm = Image.fromarray((arr * gate).astype(np.uint8), mode="L")
            v_gold = artext.apply_gold_leaf(vm, sheen_pos=sheen_pos, glow_radius=16, bevel=1.25)
        else:
            v_gold = _cached_gold_part(font_path, size, False, s_step)

        if opacity < 0.999:
            v_gold = v_gold.copy()
            v_gold.putalpha(v_gold.getchannel("A").point(lambda p: int(p * opacity)))
        canvas.alpha_composite(v_gold, (ox, oy))

    # 3. Nuqta diamond gold-leaf render (with optional scale pulse)
    if nuqta_scale > 0.01:
        n_gold = _cached_gold_part(font_path, size, True, max(0, s_step - 3))
        if abs(nuqta_scale - 1.0) > 0.015:
            r = int(size * 0.22)
            bx0, by0 = max(0, int(ncx - r)), max(0, int(ncy - r))
            bx1, by1 = min(cw, int(ncx + r)), min(ch, int(ncy + r))
            sub = n_gold.crop((bx0, by0, bx1, by1))
            sw = max(2, int(round(sub.width * nuqta_scale)))
            sh_h = max(2, int(round(sub.height * nuqta_scale)))
            sub = sub.resize((sw, sh_h), Image.LANCZOS)
            if opacity < 0.999:
                sub.putalpha(sub.getchannel("A").point(lambda p: int(p * opacity)))
            canvas.alpha_composite(sub, (int(round(world_nx - sw / 2)), int(round(world_ny - sh_h / 2))))
        else:
            if opacity < 0.999:
                n_gold = n_gold.copy()
                n_gold.putalpha(n_gold.getchannel("A").point(lambda p: int(p * opacity)))
            canvas.alpha_composite(n_gold, (ox, oy))

    return world_nx, world_ny


# --------------------------------------------------------------------------- #
# 3. Sacred Islamic Geometry Primitives
# --------------------------------------------------------------------------- #
def draw_islamic_rosette(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    radius: float,
    folds: int = 8,
    rot: float = 0.0,
    color=(216, 174, 92, 160),
    width: int = 2,
    progress: float = 1.0,
):
    """Draw classic compass-and-straightedge star polygon & concentric circles."""
    if progress <= 0.01 or radius <= 2:
        return
    # Outer & inner compass rings
    steps = max(12, int(96 * min(1.0, progress)))
    pts_circle = [
        (cx + radius * math.cos(rot + 2 * math.pi * i / 96),
         cy + radius * math.sin(rot + 2 * math.pi * i / 96))
        for i in range(steps + 1)
    ]
    if len(pts_circle) > 1:
        draw.line(pts_circle, fill=color, width=width)

    # Interlocking rotated squares / star polygons (Rub el Hizb / Shamsa)
    step = 3 if folds >= 8 else 2
    verts = [
        (cx + radius * math.cos(rot + 2 * math.pi * k / folds),
         cy + radius * math.sin(rot + 2 * math.pi * k / folds))
        for k in range(folds)
    ]
    total_edges = folds
    n_edges = int(math.ceil(total_edges * min(1.0, progress)))
    for k in range(n_edges):
        p0 = verts[k]
        p1 = verts[(k + step) % folds]
        frac = min(1.0, (progress * total_edges) - k)
        pend = (p0[0] + (p1[0] - p0[0]) * frac, p0[1] + (p1[1] - p0[1]) * frac)
        draw.line([p0, pend], fill=color, width=width)


def draw_fourfold_square(
    canvas: Image.Image,
    cx: float,
    cy: float,
    half_side: float,
    progress: float,
    pulse: float = 0.0,
):
    """Draw the Scene 2 four-cornered sacred square (هندسة مربعة ذات أربعة أركان)."""
    if progress <= 0.01:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    s = half_side
    corners = [
        (cx - s, cy - s),
        (cx + s, cy - s),
        (cx + s, cy + s),
        (cx - s, cy + s),
    ]
    gold_line = (224, 182, 98, int(205 * min(1.0, progress * 1.3)))
    bronze_line = (168, 122, 64, int(145 * min(1.0, progress)))

    # Inscribed & circumscribed circles
    r_in = s
    r_out = s * math.sqrt(2) * 0.82
    d.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], outline=bronze_line, width=2)
    if progress > 0.35:
        d.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out], outline=(168, 122, 64, 90), width=1)

    # Progressive 4 sides of the square
    for i in range(4):
        seg_p = smoothstep(i * 0.16, i * 0.16 + 0.24, progress)
        if seg_p > 0:
            p0 = corners[i]
            p1 = corners[(i + 1) % 4]
            pe = (p0[0] + (p1[0] - p0[0]) * seg_p, p0[1] + (p1[1] - p0[1]) * seg_p)
            d.line([p0, pe], fill=gold_line, width=4)
            # Inner parallel hairline
            s2 = s * 0.92
            c2_0 = (cx + (p0[0] - cx) * 0.92, cy + (p0[1] - cy) * 0.92)
            c2_1 = (cx + (pe[0] - cx) * 0.92, cy + (pe[1] - cy) * 0.92)
            d.line([c2_0, c2_1], fill=bronze_line, width=2)

    # Subtle sacred diagonals
    diag_p = smoothstep(0.55, 0.95, progress)
    if diag_p > 0:
        for i in range(2):
            p0, p1 = corners[i], corners[i + 2]
            pe = (p0[0] + (p1[0] - p0[0]) * diag_p, p0[1] + (p1[1] - p0[1]) * diag_p)
            d.line([p0, pe], fill=(212, 168, 86, 72), width=1)

    # Four glowing corner nodes (الأركان الأربعة)
    for idx, (vx, vy) in enumerate(corners):
        cp = smoothstep(0.12 * idx, 0.12 * idx + 0.25, progress)
        if cp > 0:
            orb_r = (11.0 + 3.0 * math.sin(pulse * 2.5 + idx)) * cp
            d.ellipse([vx - orb_r * 2.3, vy - orb_r * 2.3, vx + orb_r * 2.3, vy + orb_r * 2.3],
                      fill=(230, 180, 86, int(75 * cp)))
            d.ellipse([vx - orb_r, vy - orb_r, vx + orb_r, vy + orb_r],
                      fill=(255, 244, 204, int(235 * cp)), outline=(212, 168, 82, 255), width=2)

    glow = layer.filter(ImageFilter.GaussianBlur(5))
    canvas.alpha_composite(glow)
    canvas.alpha_composite(layer)


# --------------------------------------------------------------------------- #
# 4. Scene 4: 30 FPS Particle-to-«ب» Alchemical Condensation
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=2)
def _baa_particle_targets(font_path: str, size: int = 540, n_pts: int = 1350):
    """Sample `n_pts` points uniformly inside & along the vector glyph of «ب»."""
    anat, v_mask, n_mask = _cached_baa_masks(font_path, size)
    combined = ImageChops.lighter(v_mask, n_mask)
    arr = np.asarray(combined, dtype=np.float32)
    # Boost edge probability so outline is razor-sharp when particles lock in
    edge = np.asarray(combined.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    prob = arr * 0.45 + edge * 1.65
    ys, xs = np.where(prob > 25)
    weights = prob[ys, xs]
    weights = weights / weights.sum()

    rng = np.random.default_rng(42)
    idx = rng.choice(len(xs), size=n_pts, replace=True, p=weights)
    cw, ch = anat["width"], anat["height"]
    tx = xs[idx].astype(np.float32) - cw / 2.0
    ty = ys[idx].astype(np.float32) - ch / 2.0

    # Intermediate sacred octagon-lattice coordinates
    angles = rng.uniform(0, 2 * math.pi, n_pts).astype(np.float32)
    rings = rng.choice([95.0, 165.0, 235.0, 295.0], size=n_pts, p=[0.2, 0.3, 0.3, 0.2]).astype(np.float32)
    # Snap some particles to 8-pointed star chords
    k = rng.integers(0, 8, size=n_pts)
    u = rng.uniform(0, 1, size=n_pts).astype(np.float32)
    a0 = k * (2 * math.pi / 8)
    a1 = ((k + 3) % 8) * (2 * math.pi / 8)
    gx = (1 - u) * np.cos(a0) * 265 + u * np.cos(a1) * 265
    gy = (1 - u) * np.sin(a0) * 265 + u * np.sin(a1) * 265
    use_ring = rng.random(n_pts) < 0.35
    gx = np.where(use_ring, np.cos(angles) * rings, gx).astype(np.float32)
    gy = np.where(use_ring, np.sin(angles) * rings, gy).astype(np.float32)

    # Initial rising golden sand spiral coordinates (from lower bronze balance pan)
    s_ang = rng.uniform(0, 6 * math.pi, n_pts).astype(np.float32)
    s_h = rng.uniform(0.0, 1.0, n_pts).astype(np.float32)
    s_rad = (35.0 + 190.0 * (1.0 - s_h * 0.55)) * rng.uniform(0.65, 1.25, n_pts).astype(np.float32)
    sizes = rng.uniform(1.5, 4.2, n_pts).astype(np.float32)
    is_bright = rng.random(n_pts) > 0.72

    return tx, ty, gx, gy, s_ang, s_h, s_rad, sizes, is_bright


@lru_cache(maxsize=2)
def _alchemical_bg_vignette(cx: int, cy: int) -> Image.Image:
    vign = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vign)
    vd.ellipse([cx - 420, cy - 390, cx + 420, cy + 340], fill=(8, 7, 10, 185))
    return vign.filter(ImageFilter.GaussianBlur(68))


def render_alchemical_particles(
    canvas: Image.Image,
    font_path: str,
    t_local: float,
    dur: float,
    center_xy: tuple[float, float],
):
    """Scene 4: Golden dust -> Sacred geometric crystal -> Calligraphic «ب»."""
    tx, ty, gx, gy, s_ang, s_h, s_rad, sizes, is_bright = _baa_particle_targets(font_path, 540, 1350)
    cx, cy = center_xy

    # Phase timeline over ~11s:
    # 0.0..2.8s: Swirling golden sand rising from lower balance pan
    # 2.8..5.4s: Condensing into rotating sacred geometric lattice
    # 5.4..11.0s: Crystallizing into solid metallic gold-leaf «ب»!
    p_geo = smoothstep(1.6, 4.4, t_local)
    p_baa = smoothstep(4.2, 7.2, t_local)
    solid_baa = smoothstep(6.0, 8.0, t_local)

    # Gently dim background upper geometric wireframe as «ب» crystallizes so «ب» is the unmistakable hero
    bg_dim = smoothstep(4.0, 7.0, t_local)
    if bg_dim > 0.01:
        vign = _alchemical_bg_vignette(int(cx), int(cy))
        if bg_dim < 0.995:
            vign = vign.copy()
            vign.putalpha(vign.getchannel("A").point(lambda p: int(p * bg_dim)))
        canvas.alpha_composite(vign)

    # Stage 1: Swirling sand positions
    spin = s_ang + t_local * 1.45
    sx = np.cos(spin) * s_rad - 45.0 * (1.0 - s_h)
    sy = 360.0 - s_h * 640.0 + np.sin(spin * 0.7) * 22.0

    # Stage 2: Rotating geometric lattice positions
    g_rot = t_local * 0.28
    cg, sg = math.cos(g_rot), math.sin(g_rot)
    rx_g = gx * cg - gy * sg
    ry_g = gx * sg + gy * cg

    # Blend Stage 1 -> Stage 2 -> Stage 3 («ب»)
    x12 = sx * (1.0 - p_geo) + rx_g * p_geo
    y12 = sy * (1.0 - p_geo) + ry_g * p_geo
    px = cx + x12 * (1.0 - p_baa) + tx * p_baa
    py = cy + y12 * (1.0 - p_baa) + ty * p_baa

    # Draw smooth circular golden bokeh particles
    p_img = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(p_img)
    fade_in = smoothstep(0.0, 0.8, t_local)
    fade_particles = max(0.22, 1.0 - 0.72 * solid_baa)
    alpha_base = int(225 * fade_in * fade_particles)

    for idx in range(len(px)):
        x0, y0 = float(px[idx]), float(py[idx])
        if 4 <= x0 < W - 4 and 4 <= y0 < H - 4:
            r = float(sizes[idx]) * 0.68
            col = (255, 246, 210, alpha_base) if is_bright[idx] else (222, 174, 86, int(alpha_base * 0.85))
            pd.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=col)

    bloom = p_img.filter(ImageFilter.GaussianBlur(3.5))
    canvas.alpha_composite(bloom)
    canvas.alpha_composite(p_img)

    # Faint geometric wireframe overlay during lattice phase
    geo_vis = smoothstep(2.0, 3.8, t_local) * (1.0 - smoothstep(5.0, 6.8, t_local))
    if geo_vis > 0.02:
        gl = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(gl)
        draw_islamic_rosette(
            gd, cx, cy, 268, folds=8, rot=g_rot,
            color=(218, 176, 94, int(145 * geo_vis)), width=2, progress=1.0,
        )
        canvas.alpha_composite(gl)

    # Solid embossed gold «ب» crystallizing as particles settle
    if solid_baa > 0.01:
        sheen = 0.25 + 0.55 * ((t_local - 6.0) / 4.5)
        render_hero_baa(
            canvas, font_path, center_xy, size=540,
            vessel_reveal=1.0, nuqta_scale=1.0,
            nuqta_glow=1.15 * solid_baa, sheen_pos=sheen,
            opacity=solid_baa, rot_rays=t_local * 0.18,
        )


# --------------------------------------------------------------------------- #
# 5. Scene 5: Cosmic Harmonic Waves, 3D Sacred Polyhedra & Background «ب»
# --------------------------------------------------------------------------- #
def _icosahedron_geometry():
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [
        (-1,  phi, 0), ( 1,  phi, 0), (-1, -phi, 0), ( 1, -phi, 0),
        (0, -1,  phi), (0,  1,  phi), (0, -1, -phi), (0,  1, -phi),
        ( phi, 0, -1), ( phi, 0,  1), (-phi, 0, -1), (-phi, 0,  1),
    ]
    verts = [tuple(c / math.sqrt(1 + phi * phi) for c in v) for v in verts]
    edges = []
    for i in range(len(verts)):
        for j in range(i + 1, len(verts)):
            dist = math.dist(verts[i], verts[j])
            if abs(dist - 2.0 / math.sqrt(1 + phi * phi)) < 0.08:
                edges.append((i, j))
    return verts, edges


_ICO_VERTS, _ICO_EDGES = _icosahedron_geometry()


def render_cosmic_scene(
    canvas: Image.Image,
    font_path: str,
    t_local: float,
    dur: float,
):
    """Scene 5: Converging light waves + luminous spheres + 3D polyhedron + monumental background «ب»."""
    cx, cy = W / 2, H * 0.50

    # 1. Monumental spectral golden «ب» emerging in the deep cosmic background
    baa_op = 0.34 * smoothstep(1.2, 4.5, t_local)
    if baa_op > 0.01:
        render_hero_baa(
            canvas, font_path, (cx, cy - 30), size=760,
            vessel_reveal=smoothstep(1.0, 4.2, t_local),
            nuqta_scale=1.0,
            nuqta_glow=0.75,
            sheen_pos=0.35 + 0.35 * math.sin(t_local * 0.5),
            opacity=baa_op,
            rot_rays=t_local * 0.10,
        )

    # 2. Converging harmonic light wave rings (موجات ضوئية تتجمع في مركز واحد)
    wave_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave_layer)
    for k in range(7):
        phase = ((k / 7.0) - t_local * 0.20) % 1.0
        r = 40.0 + phase * 490.0
        alpha = int(135 * math.sin(phase * math.pi) ** 1.4)
        col = (255, 244, 214, alpha) if k % 2 == 0 else (218, 174, 90, alpha)
        wd.ellipse([cx - r, cy - r * 0.62, cx + r, cy + r * 0.62], outline=col, width=2)
    wave_layer = wave_layer.filter(ImageFilter.GaussianBlur(1.5))
    canvas.alpha_composite(wave_layer)

    # 3. Rotating 3D sacred icosahedron + orbiting luminous spheres at nexus
    poly_p = smoothstep(2.0, 5.2, t_local)
    if poly_p > 0.02:
        pl = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        pd = ImageDraw.Draw(pl)
        ax, ay = t_local * 0.42, t_local * 0.58
        cax, sax = math.cos(ax), math.sin(ax)
        cay, say = math.cos(ay), math.sin(ay)
        scale = 148.0 * (0.75 + 0.25 * poly_p)

        proj = []
        for vx, vy, vz in _ICO_VERTS:
            # Rotate Y then X
            x1 = vx * cay + vz * say
            z1 = -vx * say + vz * cay
            y2 = vy * cax - z1 * sax
            z2 = vy * sax + z1 * cax
            persp = 3.2 / (3.2 - z2 * 0.65)
            proj.append((cx + x1 * scale * persp, cy + y2 * scale * persp, z2))

        for i, j in _ICO_EDGES:
            x0, y0, z0 = proj[i]
            x1, y1, z1 = proj[j]
            depth_a = int((110 + 95 * ((z0 + z1) * 0.5 + 1.0) * 0.5) * poly_p)
            pd.line([(x0, y0), (x1, y1)], fill=(238, 198, 118, depth_a), width=2)

        for x0, y0, z0 in proj:
            sr = (3.5 + 2.2 * (z0 + 1.0)) * poly_p
            pd.ellipse([x0 - sr, y0 - sr, x0 + sr, y0 + sr], fill=(255, 248, 220, int(220 * poly_p)))

        # Orbiting luminous spheres (كرات ضوئية)
        for s_i in range(5):
            ang = t_local * (0.55 + 0.08 * s_i) + s_i * (2 * math.pi / 5)
            orb_r = 215.0 + 38.0 * math.sin(t_local * 0.9 + s_i)
            sx = cx + math.cos(ang) * orb_r
            sy = cy + math.sin(ang) * orb_r * 0.68
            rad = (10.0 + 3.0 * (s_i % 2)) * poly_p
            pd.ellipse([sx - rad * 2.2, sy - rad * 2.2, sx + rad * 2.2, sy + rad * 2.2],
                       fill=(228, 182, 92, int(72 * poly_p)))
            pd.ellipse([sx - rad, sy - rad, sx + rad, sy + rad],
                       fill=(255, 249, 228, int(235 * poly_p)))

        canvas.alpha_composite(pl.filter(ImageFilter.GaussianBlur(4)))
        canvas.alpha_composite(pl)


# --------------------------------------------------------------------------- #
# 6. Scene 7: Academy of the Key of the Seven Secrets Emblem
# --------------------------------------------------------------------------- #
def render_academy_emblem(
    canvas: Image.Image,
    font_path: str,
    cx: float,
    cy: float,
    t_local: float,
    baa_font_size: int = 340,
):
    """Render golden «ب» remaining at center + Seven-Pointed Key Emblem of the Academy."""
    seal_p = smoothstep(1.8, 5.0, t_local)

    if seal_p > 0.01:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        rot = -math.pi / 2 + t_local * 0.06
        r_outer = 248.0
        r_inner = 196.0
        gold_a = int(215 * seal_p)
        soft_a = int(125 * seal_p)

        # Double antique-gold seal rings
        d.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
                  outline=(226, 184, 102, gold_a), width=3)
        d.ellipse([cx - r_outer - 12, cy - r_outer - 12, cx + r_outer + 12, cy + r_outer + 12],
                  outline=(176, 130, 62, soft_a), width=1)
        d.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner],
                  outline=(198, 152, 76, soft_a), width=2)

        # Sacred Heptagram — 7-pointed star of the Seven Secrets (مفتاح الأسرار السبعة)
        verts7 = [
            (cx + r_outer * math.cos(rot + 2 * math.pi * k / 7),
             cy + r_outer * math.sin(rot + 2 * math.pi * k / 7))
            for k in range(7)
        ]
        for k in range(7):
            d.line([verts7[k], verts7[(k + 2) % 7]], fill=(232, 190, 108, int(175 * seal_p)), width=2)
            d.line([verts7[k], verts7[(k + 3) % 7]], fill=(184, 138, 66, int(105 * seal_p)), width=1)
            vx, vy = verts7[k]
            d.ellipse([vx - 6, vy - 6, vx + 6, vy + 6], fill=(255, 245, 210, gold_a))

        # Ceremonial Golden Key shaft descending beneath the central emblem bow
        shaft_top = cy + r_inner * 0.72
        shaft_bot = cy + r_outer + 118
        key_col = (228, 186, 102, gold_a)
        d.line([(cx, shaft_top), (cx, shaft_bot)], fill=key_col, width=6)
        d.ellipse([cx - 10, shaft_bot - 6, cx + 10, shaft_bot + 14], outline=key_col, width=3)
        # Key teeth (3 symbolic wards on right side)
        for ty, tw in [(shaft_bot - 22, 34), (shaft_bot - 40, 22), (shaft_bot - 58, 34)]:
            d.line([(cx, ty), (cx + tw, ty)], fill=key_col, width=5)

        canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(4)))
        canvas.alpha_composite(layer)

    # Persistent golden «ب» & glowing Nuqta at the exact heart of the Academy's Key bow
    scale_k = 1.0 - 0.24 * seal_p
    cur_size = int(round(baa_font_size / 0.76 * scale_k))
    render_hero_baa(
        canvas,
        font_path,
        (cx, cy - 12 * seal_p),
        size=cur_size,
        vessel_reveal=1.0,
        nuqta_scale=1.0 + 0.08 * math.sin(t_local * 2.4),
        nuqta_glow=1.05,
        sheen_pos=0.35 + 0.4 * math.sin(t_local * 0.8),
        opacity=1.0,
        rot_rays=t_local * 0.15,
    )


# --------------------------------------------------------------------------- #
# 7. Master Per-Scene VFX Compositor + Illuminated Top Title Banner
# --------------------------------------------------------------------------- #
def render_scene_vfx(
    frame: Image.Image,
    scene: dict,
    t_global: float,
    font_callig: str,
    font_title: str,
):
    """Apply active scene's bespoke calligraphic, geometric & particle VFX at 30fps."""
    mode = scene["vfx_mode"]
    t_local = t_global - scene["start"]
    dur = scene["end"] - scene["start"]
    sheen = 0.22 + 0.58 * ((t_local / max(1.0, dur)) % 1.0)

    if mode == "hook_nuqta_genesis":
        # 0..0.40s: Absolute darkness -> shocking golden Nuqta ignition at t=0.42s!
        dark_veil = 1.0 - smoothstep(0.35, 1.45, t_local)
        if dark_veil > 0.01:
            veil = Image.new("RGBA", frame.size, (6, 5, 8, int(255 * dark_veil)))
            frame.alpha_composite(veil)

        ignite = smoothstep(0.36, 0.62, t_local)
        shock = smoothstep(0.42, 2.10, t_local)
        if 0.01 < shock < 0.99:
            sl = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            sd = ImageDraw.Draw(sl)
            sr = 24.0 + shock * 520.0
            sa = int(210 * (1.0 - shock) ** 1.5)
            sd.ellipse([W / 2 - sr, H / 2 - sr, W / 2 + sr, H / 2 + sr],
                       outline=(255, 238, 184, sa), width=3)
            frame.alpha_composite(sl.filter(ImageFilter.GaussianBlur(3)))

        # Nuqta turns into sacred geometric energy mandala
        geo_p = smoothstep(3.1, 5.8, t_local)
        if geo_p > 0.01:
            gl = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            gd = ImageDraw.Draw(gl)
            draw_islamic_rosette(
                gd, W / 2, H * 0.53, 290.0 * (0.7 + 0.3 * geo_p),
                folds=8, rot=t_local * 0.16,
                color=(224, 182, 96, int(175 * geo_p)), width=2, progress=geo_p,
            )
            draw_islamic_rosette(
                gd, W / 2, H * 0.53, 185.0,
                folds=16, rot=-t_local * 0.12,
                color=(188, 140, 68, int(130 * geo_p)), width=1, progress=geo_p,
            )
            frame.alpha_composite(gl)

        vessel_p = smoothstep(2.15, 4.45, t_local)
        if ignite > 0.01:
            render_hero_baa(
                frame, font_callig, (W / 2, H * 0.47), size=560,
                vessel_reveal=vessel_p,
                nuqta_scale=0.55 + 0.45 * ignite + 0.08 * math.sin(t_local * 3.2),
                nuqta_glow=1.35 * ignite,
                sheen_pos=sheen,
                opacity=1.0,
                rot_rays=t_local * 0.22,
            )

    elif mode == "manuscript_square_two":
        cx, cy = W / 2, H * 0.50
        sq_p = smoothstep(2.2, 6.2, t_local)
        draw_fourfold_square(frame, cx, cy, half_side=285.0, progress=sq_p, pulse=t_local)

        baa_in = smoothstep(0.4, 2.0, t_local)
        render_hero_baa(
            frame, font_callig, (cx, cy - 28), size=470,
            vessel_reveal=smoothstep(0.5, 2.4, t_local),
            nuqta_scale=1.0,
            nuqta_glow=0.85 * baa_in,
            sheen_pos=sheen,
            opacity=baa_in,
            rot_rays=t_local * 0.14,
        )

        # Embossed golden numeral «٢ | 2» inside a royal circular medallion above the square
        num_p = smoothstep(1.6, 3.4, t_local)
        if num_p > 0.02:
            med_y = int(cy - 372)
            med = Image.new("RGBA", (220, 110), (0, 0, 0, 0))
            md = ImageDraw.Draw(med)
            md.rounded_rectangle(
                [8, 12, 212, 98], radius=44,
                fill=(10, 9, 13, int(195 * num_p)),
                outline=(214, 172, 90, int(190 * num_p)), width=2,
            )
            num_img = artext.render_gold_text("٢  ·  2", font_title, 58, sheen_pos=sheen, glow_radius=9)
            num_img.putalpha(num_img.getchannel("A").point(lambda p: int(p * num_p)))
            med.alpha_composite(num_img, ((220 - num_img.width) // 2, (110 - num_img.height) // 2))
            frame.alpha_composite(med, (int(cx - 110), med_y - 55))

    elif mode == "macro_nuqta_filaments":
        cx, cy = W / 2, H * 0.52
        # First sub-shot: macro focus on Nuqta beneath ghostly golden «ب»; second: branching cosmic filaments
        branch_p = smoothstep(4.2, 9.2, t_local)
        if branch_p > 0.01:
            fl = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            fd = ImageDraw.Draw(fl)
            n_rays = 24
            for i in range(n_rays):
                ang = -math.pi / 2 + (i - n_rays / 2) * (2 * math.pi / n_rays) + math.sin(i * 1.7) * 0.04
                max_len = 860.0 if i % 2 == 0 else 580.0
                cur_len = max_len * smoothstep(0.02 * (i % 8), 0.75 + 0.02 * (i % 8), branch_p)
                ex = cx + math.cos(ang) * cur_len
                ey = cy + math.sin(ang) * cur_len
                alpha = int((175 if i % 3 == 0 else 95) * branch_p)
                fd.line([(cx, cy), (ex, ey)], fill=(236, 192, 104, alpha), width=2 if i % 3 == 0 else 1)
                # Traveling light node along ray
                photon_u = ((t_local * 0.38 + i * 0.13) % 1.0) * branch_p
                px = cx + math.cos(ang) * (cur_len * photon_u)
                py = cy + math.sin(ang) * (cur_len * photon_u)
                fd.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(255, 248, 222, int(210 * branch_p)))
            draw_islamic_rosette(
                fd, cx, cy, 145.0, folds=12, rot=t_local * 0.18,
                color=(240, 200, 118, int(205 * branch_p)), width=2, progress=branch_p,
            )
            frame.alpha_composite(fl.filter(ImageFilter.GaussianBlur(2)))
            frame.alpha_composite(fl)

        # Upper vessel fades gracefully into macro bokeh while Nuqta dominates center
        vessel_op = max(0.22, 1.0 - 0.68 * smoothstep(1.2, 5.2, t_local))
        # Shift «ب» up slightly so Nuqta sits right near focal center (cx, cy)
        anat, _, _ = _cached_baa_masks(font_callig, 620)
        dy_nuqta = anat["nuqta_center"][1] - anat["height"] / 2
        baa_im = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        render_hero_baa(
            baa_im, font_callig, (cx, cy - dy_nuqta), size=620,
            vessel_reveal=1.0,
            nuqta_scale=1.18 + 0.10 * math.sin(t_local * 2.8),
            nuqta_glow=1.35,
            sheen_pos=sheen,
            opacity=vessel_op,
            rot_rays=t_local * 0.20,
        )
        frame.alpha_composite(baa_im)

    elif mode == "alchemical_particle_baa":
        render_alchemical_particles(frame, font_callig, t_local, dur, (W / 2, H * 0.45))

    elif mode == "cosmic_waves_polyhedra":
        render_cosmic_scene(frame, font_callig, t_local, dur)

    elif mode == "sovereign_arabesque_baa":
        cx, cy = W / 2, H * 0.44
        orn_p = smoothstep(0.8, 5.5, t_local)
        if orn_p > 0.01:
            ol = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            od = ImageDraw.Draw(ol)
            for rad, folds, spd, al in [
                (355.0, 12,  0.07, 155),
                (275.0, 16, -0.09, 135),
                (195.0,  8,  0.11, 165),
            ]:
                draw_islamic_rosette(
                    od, cx, cy, rad, folds=folds, rot=t_local * spd,
                    color=(224, 180, 96, int(al * orn_p)), width=2, progress=orn_p,
                )
            frame.alpha_composite(ol.filter(ImageFilter.GaussianBlur(2)))
            frame.alpha_composite(ol)

        baa_in = smoothstep(0.3, 2.2, t_local)
        render_hero_baa(
            frame, font_callig, (cx, cy), size=620,
            vessel_reveal=smoothstep(0.3, 2.4, t_local),
            nuqta_scale=1.06 + 0.07 * math.sin(t_local * 2.4),
            nuqta_glow=1.30 * baa_in,
            sheen_pos=sheen,
            opacity=baa_in,
            rot_rays=t_local * 0.14,
        )

    elif mode == "closing_academy_seal":
        render_academy_emblem(frame, font_callig, W / 2, H * 0.45, t_local, baa_font_size=340)


@lru_cache(maxsize=16)
def _cached_title_banner(lines_tuple: tuple[str, ...], font_path: str) -> Image.Image:
    """Pre-render royal manuscript ornamental scene header with soft obsidian contrast veil."""
    imgs = []
    for i, ln in enumerate(lines_tuple):
        sz = 54 if i == 0 else 38
        imgs.append(artext.render_gold_text(ln, font_path, sz, max_width=880, sheen_pos=0.52, glow_radius=11))

    w = max(im.width for im in imgs) + 150
    h = sum(im.height for im in imgs) + 52
    banner = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # Soft feathered charcoal-obsidian backing so gold calligraphy pops over bright god-rays
    bg = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg)
    bd.rounded_rectangle([14, 6, w - 14, h - 6], radius=28, fill=(8, 7, 11, 176))
    bg = bg.filter(ImageFilter.GaussianBlur(10))
    banner = Image.alpha_composite(banner, bg)

    d = ImageDraw.Draw(banner)
    # Subtle top & bottom ornamental gold rules with diamond finials
    line_col = (218, 174, 92, 185)
    d.line([(34, 14), (w - 34, 14)], fill=line_col, width=2)
    d.line([(64, h - 12), (w - 64, h - 12)], fill=(188, 142, 68, 145), width=1)
    for dx in (28, w - 28):
        d.polygon([(dx, 8), (dx + 6, 14), (dx, 20), (dx - 6, 14)], fill=(248, 214, 138, 230))

    y = 22
    for im in imgs:
        banner.alpha_composite(im, ((w - im.width) // 2, y))
        y += im.height - 6
    return banner


def draw_scene_banner(frame: Image.Image, scene: dict, t_global: float, font_title: str):
    t_local = t_global - scene["start"]
    dur = scene["end"] - scene["start"]
    alpha = smoothstep(0.45, 1.35, t_local) * (1.0 - smoothstep(dur - 0.85, dur - 0.10, t_local))
    # Keep final Academy CTA visible right until final fade
    if scene["id"] == "S07":
        alpha = smoothstep(0.55, 1.50, t_local) * (1.0 - smoothstep(dur - 0.55, dur - 0.05, t_local))
    if alpha <= 0.01:
        return
    banner = _cached_title_banner(tuple(scene["on_screen_title"]), font_title)
    if alpha < 0.999:
        b = banner.copy()
        b.putalpha(b.getchannel("A").point(lambda p: int(p * alpha)))
    else:
        b = banner
    x = (W - b.width) // 2
    y = 178 if len(scene["on_screen_title"]) == 1 else 156
    frame.alpha_composite(b, (x, y))
