---
layout: section
title: Microscopy volumes
description: Calibrated microscopy and segmentation volumes, sections, slabs, channels, label contours and measurements in inklet.volume.
groups:
  - title: Calibrated volumes
    text: Volumes keep voxel spacing and origin attached to image and segmentation arrays. Install the volume extra.
    cards:
      - title: Calibrated volumes
        page: calibrated-volumes.md
        image: assets/guides/calibrated-volumes-3.png
        text: Crops, slices, scale bars, measured volumes and surfaces in physical coordinates.
      - title: Oblique sections
        page: oblique-sections.md
        image: assets/guides/oblique-sections-2.png
        text: Sample an arbitrarily oriented plane with its own scale bar and 3D outline.
      - title: Slab projections and regions
        page: slabs-and-regions.md
        image: assets/guides/slabs-and-regions-1.png
        text: Finite-thickness projections and one box region shared by every view.
      - title: Channels and contours
        page: channels-and-contours.md
        image: assets/guides/channels-and-contours-1.png
        text: Channel composites and exact vector contours of segmentation labels.
  - title: Measurements and files
    cards:
      - title: Per-label intensities
        page: label-measurements.md
        text: measure_labels returns per-label intensity statistics from calibrated volumes.
      - title: TIFF import
        page: microscopy-tiff.md
        text: Read microscopy TIFF files into calibrated Volume objects.
  - title: Microscopy examples
    text: Complete figures from public microscopy data.
    cards:
      - title: Real microscopy and organelles
        page: real-biology.md
        image: gallery/real-biology.png
        text: FIB-SEM sections, organelle surfaces and volume charts from one HeLa crop.
      - title: Shared oblique planes
        page: oblique-biology.md
        image: gallery/oblique-biology.png
        text: Two physical planes shown in a 3D scene, as sections and as measurements.
      - title: Linked slab regions
        page: slab-biology.md
        image: gallery/slab-biology.png
        text: Slab projections and one region box across nine panels.
      - title: Fluorescence channels
        page: fluorescence-biology.md
        image: gallery/fluorescence-biology.png
        text: Two-channel fluorescence with composites, contours, profiles and areas.
      - title: Labels to intensity plots
        page: label-intensities.md
        image: gallery/label-intensities.png
        text: Segmentation labels, region zooms and per-label intensity statistics.
---
# Microscopy volumes

`inklet.volume` keeps voxel spacing, origin and source identity attached to
microscopy and segmentation arrays, so sections, slab projections, contours,
scale bars and measurements share one physical coordinate frame. Install it
with `python -m pip install 'inklet[volume]'`; `import inklet` does not load it.

The package is stable from 4.3 and follows the
[compatibility policy](compatibility.md#api-and-saved-file-policy). The
`inklet.experimental` paths used before 4.3 still work and return the same
objects. See the [API reference](api.md#inkletvolume) for every name.

<!-- cards -->
