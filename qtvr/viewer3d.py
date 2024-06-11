"""
Code to view panorama scenes and their hotspots.

run with from within this directory: `python3 viewer3d.py`

Press `h` to show and unshow the hotspot track.

Note: Firstly create the images by running the make_mosaic script
on the panorama QTVR files.

These are hardcoded. Change CYLINDER_IMAGE and HOTSPOT_IMAGE to 
the name of the file you want to view.

Secondly, use the following code in a shell to create a transparent hotspot image:

from PIL import Image

img = Image.open('img.png')
img = img.convert("RGBA")

pixdata = img.load()

width, height = img.size
for y in range(height):
    for x in range(width):
        if pixdata[x, y] == (255, 255, 255, 255):
            pixdata[x, y] = (255, 255, 255, 0)

img.save("img2.png", "PNG")⏎  

"""

CYLINDER_IMAGE = "scene.png"
HOTSPOT_IMAGE = "scene-hotspot.png"

import time

import numpy as np
import pygfx as gfx
from PIL import Image
from scipy.spatial.transform import Rotation
from wgpu.gui.auto import WgpuCanvas

scene = gfx.Scene()


def create_cylinder(filename: str) -> gfx.Mesh:
    geo = gfx.cylinder_geometry(
        height=2, radial_segments=32, height_segments=4, open_ended=True
    )
    # im = iio.imread(filename).astype("float32") / 255
    im = np.asarray(Image.open(filename))
    tex = gfx.Texture(im, dim=2)
    material = gfx.MeshBasicMaterial(map=tex)
    cyl = gfx.Mesh(geo, material)
    cyl.local.rotation = Rotation.from_euler("XYZ", [90, 0, 0], degrees=True).as_quat()
    return cyl


sceneTrack = create_cylinder(CYLINDER_IMAGE)
hotspotTrack = create_cylinder(HOTSPOT_IMAGE)
hotspotTrack.visible = False

# add hotspotTrack first, this way it gets preference when rendering.
# When showing the hotspot track the hotspot track needs to be drawn on top of the scene track.
scene.add(hotspotTrack)
scene.add(sceneTrack)

canvas = None
renderer = None
controller = None
camera = None
before_render = None
after_render = None
draw_function = None
up = (0, 1, 0)

canvas = WgpuCanvas()
renderer = gfx.renderers.WgpuRenderer(canvas)

camera = gfx.PerspectiveCamera(70, 4 / 3)
camera.local.position = (0, 0, 0)


class FixedController(gfx.Controller):
    _default_controls = {"mouse1": ("pan", "drag", (1, 1))}

    # initial state
    horizontal_position = 0
    vertical_position = 0

    def _update_pan(self, delta, *, vecx, vecy):
        # These update methods all accept one positional arg: the delta.
        # it can additionally require keyword args, from a set of names
        # that new actions store. These include:
        # rect, screen_pos, vecx, vecy

        assert isinstance(delta, tuple) and len(delta) == 2

        # print(f"vecx: {vecx} vecy: {vecy}")
        # print(f"delta {delta}")

        self.horizontal_position += -vecx[0] * delta[0]
        self.vertical_position += vecy[1] * delta[1]

        X = self.vertical_position
        Y = self.horizontal_position
        Z = 0

        # print(f"XYZ: {X} {Y} {Z}")
        rotation = Rotation.from_euler("YXZ", [Y, X, Z], degrees=True)
        self._set_camera_state({"rotation": rotation.as_quat()})


def on_key_down(event):
    if event.key == "h":
        hotspotTrack.visible = not hotspotTrack.visible


renderer.add_event_handler(on_key_down, "key_down")

controller = FixedController(camera, register_events=renderer)


class CameraStats(gfx.Stats):
    def __init__(self, viewport):
        super().__init__(viewport)
        self.bg.local.scale = (180, self._line_height * 3.1, 1)

    def stop(self):
        if not self._init:
            self._init = True
            return

        t = time.perf_counter_ns()
        self._frames += 1

        delta = round((t - self._tbegin) / 1_000_000)
        self._tmin = min(self._tmin, delta)
        self._tmax = max(self._tmax, delta)

        if t >= self._tprev + 1_000_000_000:
            # update FPS counter whenever a second has passed
            fps = round(self._frames / ((t - self._tprev) / 1_000_000_000))
            self._tprev = t
            self._frames = 0
            self._fmin = min(self._fmin, fps)
            self._fmax = max(self._fmax, fps)
            self._fps = fps

        text = f"{delta} ms ({self._tmin}-{self._tmax})"
        if self._fps is not None:
            text += f"\n{self._fps} fps ({self._fmin}-{self._fmax})"
        text += f"\nX: {controller.vertical_position:.4f} Y: {controller.horizontal_position:4f}"
        self.stats_text.geometry.set_text(text)


stats = CameraStats(renderer)

if __name__ == "__main__":
    gfx.Display(
        canvas,
        renderer,
        controller,
        camera,
        before_render,
        after_render,
        draw_function,
        stats=stats,
    ).show(scene, up)
