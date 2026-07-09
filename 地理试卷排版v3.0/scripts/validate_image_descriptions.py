#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验 image_descriptions.json 字段与 images/ 实际文件是否一致。
"""
import json
import os
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="Validate image_descriptions.json")
    parser.add_argument("--images-dir", default="output/{试卷名称}/清洗产物/images", help="图片目录")
    parser.add_argument("--json", default="output/{试卷名称}/中间数据/image_descriptions.json", help="图片描述 JSON")
    parser.add_argument("--schema", default="schemas/exam_paper.schema.json", help="统一 Schema")
    args = parser.parse_args()

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    img_dir = os.path.join(base, args.images_dir)
    data_path = os.path.join(base, args.json)
    schema_path = os.path.join(base, args.schema)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    image_schema = schema["properties"]["images"]["items"]
    allowed_types = set(image_schema["properties"]["type"]["enum"])
    required = set(image_schema["required"])

    files = [f for f in os.listdir(img_dir) if os.path.isfile(os.path.join(img_dir, f))]
    errors = []

    if data.get("image_count") != len(files):
        errors.append(f"image_count {data.get('image_count')} != actual files {len(files)}")

    if len(data.get("images", [])) != len(files):
        errors.append(f"images array length {len(data.get('images', []))} != actual files {len(files)}")

    ids = set()
    for img in data.get("images", []):
        missing = required - set(img.keys())
        if missing:
            errors.append(f"{img.get('image_id')}: missing required fields {missing}")
        if img.get("image_id") in ids:
            errors.append(f"duplicate image_id {img.get('image_id')}")
        ids.add(img.get("image_id"))
        if img.get("type") not in allowed_types:
            errors.append(f"{img.get('image_id')}: invalid type {img.get('type')}")
        if not isinstance(img.get("keywords"), list):
            errors.append(f"{img.get('image_id')}: keywords must be array")
        if not isinstance(img.get("ocr_text"), list):
            errors.append(f"{img.get('image_id')}: ocr_text must be array")
        if not isinstance(img.get("uncertain"), bool):
            errors.append(f"{img.get('image_id')}: uncertain must be boolean")

    print(f"Files in {args.images_dir}: {len(files)}")
    print(f"Images described: {len(data.get('images', []))}")
    print(f"Errors: {len(errors)}")
    for e in errors:
        print("  -", e)

    if errors:
        sys.exit(1)
    print("OK: image_descriptions.json passes field-level validation against Schema images items.")


if __name__ == "__main__":
    main()
