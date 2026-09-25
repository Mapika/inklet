---
layout: section
title: 3D and images
description: Vector 3D solids and meshes, Blender renders with vector labels, and image panels.
groups:
  - title: Built-in 3D and images
    text: The built-in renderer writes vector artwork from solids and meshes. It needs no GPU, Blender or network connection.
    cards:
      - title: Meshes and images
        page: three-images.md
        image: assets/guides/three-images-2.png
        text: Generated solids, assembled parts with depth ordering, loaded meshes and raster images in document cells.
      - title: A measured 3D part
        page: example-library.md#labelled-3d-part
        image: gallery/part.png
        text: A labelled part with dimensions from the example scripts.
  - title: Blender scenes
    text: Blender renders the pixels. Labels, leaders, dimensions and paths stay vector in SVG and PDF, and editing them does not render again.
    cards:
      - title: Blender scenes
        page: blender-scenes.md
        image: gallery/v3-scene-passes.png
        text: Use a .blend scene as a panel, with depth, normal, object ID and mask passes.
      - title: Annotations and measurements
        page: scene-annotations.md
        image: gallery/v3-scene-annotations.png
        text: Labels, arrows, length dimensions and angles placed in world coordinates.
      - title: Vector paths in scenes
        page: scene-paths.md
        image: gallery/v3-scene-paths.png
        text: Trajectories and routes hidden by scene objects according to the saved depth pass.
      - title: Scene templates
        page: scene-templates.md
        image: gallery/v3-scene-templates.png
        text: Laboratory, product and architectural scenes with named cameras and landmarks.
      - title: GPU rendering and jobs
        page: render-jobs.md
        image: gallery/v3-render-jobs.png
        text: Cycles uses an available GPU and falls back to the CPU. Queue several views, observe progress and cancel.
  - title: Worked examples
    cards:
      - title: Biological schematic
        page: scientific-scenes.md
        image: assets/scenes/synapse.png
        text: A synapse built in Blender, labelled in Inklet and placed above two plots.
      - title: Label an anatomy model
        page: open-anatomy.md
        image: assets/scenes/open-anatomy.png
        text: A freely licensed NIH 3D model rendered from two views with vector labels.
      - title: Annotated laboratory cutaway
        page: complex-scene.md
        image: gallery/v3-complex-scene.png
        text: A 265-object scene with twelve callouts, a dimension, detail views and a plot.
---
# 3D and images

A 3D panel sits in a document cell like a plot. The built-in renderer draws
solids and meshes as vector paths and resolves depth between intersecting
parts. For photographic lighting, Inklet renders a Blender scene and keeps its
annotations as vector geometry, positioned with the saved camera and depth
pass. Calibrated microscopy volumes have their own
[section](volumes.md).

<!-- cards -->

## Requirements

The built-in renderer uses the core package. Raster images use the `images`
extra. Blender scenes need a Blender installation; the
[compatibility matrix](compatibility.md) lists the tested versions. See
[installation](installation.md) for the extras.
