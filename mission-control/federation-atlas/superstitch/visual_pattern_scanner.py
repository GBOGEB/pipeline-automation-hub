#!/usr/bin/env python3
"""Pixel-edge and box-pattern QA (not OCR, not SSOT) for W34 review renders."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageFilter, ImageStat


def scan(image_path,output,expected_width=None):
    img=Image.open(image_path).convert('RGB')
    width,height=img.size
    if expected_width and width!=expected_width:raise ValueError('SCREENSHOT_WIDTH_MISMATCH')
    if width<390 or height<450:raise ValueError('UNREADABLE_OR_TOO_SMALL_RENDER')
    edges=img.convert('L').filter(ImageFilter.FIND_EDGES)
    hist=edges.histogram()
    pixels=width*height
    edge_count=sum(hist[55:]);edge_ratio=edge_count/pixels
    if edge_ratio<.005:raise ValueError('NO_STRUCTURAL_EDGES_DETECTED')
    if edge_ratio>.65:raise ValueError('OVERCOMPLEX_NOISE_LIKELY')
    mean_luma=ImageStat.Stat(img.convert('L')).mean[0]
    # Pixel measurements flag visual output characteristics only. Text detection
    # and semantic correctness remain DOM/source tests, never inferred by OCR.
    report={'schema':'missioncontrol.superstitch.visual_pattern_scan.v1',
            'image':Path(image_path).name,'sha256':hashlib.sha256(Path(image_path).read_bytes()).hexdigest(),
            'width':width,'height':height,'edge_pixels':edge_count,'edge_ratio':round(edge_ratio,6),
            'mean_luminance':round(mean_luma,3),'text_ocr_performed':False,
            'overlap_assertion':'DOM_GEOMETRY_TEST_REQUIRED',
            'status':'LOCAL_PIXEL_PATTERN_PASS',
            'native_status':None,'engineering_credit':False}
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--out',required=True);p.add_argument('--width',type=int);a=p.parse_args()
    print(json.dumps(scan(a.image,a.out,a.width),sort_keys=True))
