#!/usr/bin/env python3
"""Import the prepared INaudio retailer links into the app resources CSV."""

import argparse
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESOURCES_CSV = PROJECT_ROOT / "data" / "Resulam_resources_database.csv"
IMAGE_BASE_URL = (
    "https://resulam-images.s3.amazonaws.com/"
    "ResulamBookCoversQRCode_Compressed/Resources/Audiobooks"
)

LANGUAGES = {
    "Twi Audio Phrasebook": "Twi",
    "Yemba Audio Phrasebook": "Yemba",
    "Ewondo Audio Phrasebook": "Ewondo",
    "Bamoun (Shupamom) Language Phrasebook": "Bamoun",
    "Duala (Douala) Language Phrasebook": "Duala",
    "Chichewa Phrasebook": "Chichewa",
    "Swahili-French-English Phrasebook": "Kiswahili",
    "Ŋwɑ̀'nǐ njá'ghə̀ə̀ mɑ̀ ghə̀ə̄ – Nufi Phrasebook": "Nufi",
    "Contes africains, contes bamilékés – Nufi": "Nufi",
    "Yoruba-French-English Phrasebook": "Yoruba",
}

IMAGE_FILENAMES = {
    "Twi Audio Phrasebook": "01_twi_marketing_qr.png",
    "Yemba Audio Phrasebook": "02_yemba_marketing_qr.png",
    "Ewondo Audio Phrasebook": "03_ewondo_marketing_qr.png",
    "Bamoun (Shupamom) Language Phrasebook": "04_bamoun_marketing_qr.png",
    "Duala (Douala) Language Phrasebook": "05_duala_marketing_qr.png",
    "Chichewa Phrasebook": "06_chichewa_marketing_qr.png",
    "Swahili-French-English Phrasebook": "07_swahili_marketing_qr.png",
    "Ŋwɑ̀'nǐ njá'ghə̀ə̀ mɑ̀ ghə̀ə̄ – Nufi Phrasebook": "08_nufi_phrasebook_marketing_qr.png",
    "Contes africains, contes bamilékés – Nufi": "09_nufi_tales_marketing_qr.png",
    "Yoruba-French-English Phrasebook": "10_yoruba_marketing_qr.png",
}

RETAILER_COLORS = {
    "Apple": "secondary",
    "Google Play": "success",
    "Spotify": "success",
    "Kobo": "info",
    "Kobo, Walmart": "info",
}

BASE_FIELDS = [
    "name",
    "category",
    "language",
    "publication_date",
    "image",
    "image_fit",
    "display_in_purchase",
    "description",
]


def ordered_links(item):
    """Put the primary retailer first while retaining every unique retailer URL."""
    result = [{
        "retailer": item["primary_qr_retailer"],
        "url": item["primary_qr_link"],
    }]
    seen_urls = {item["primary_qr_link"]}
    for link in item["all_retailer_links"]:
        if link["url"] not in seen_urls:
            result.append(link)
            seen_urls.add(link["url"])
    return result


def import_resources(kit_dir, resources_csv):
    source_path = kit_dir / "referral-links.json"
    prepared = json.loads(source_path.read_text(encoding="utf-8"))

    with resources_csv.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        existing = [
            row for row in reader
            if row.get("category", "").strip() != "Audiobooks"
        ]
        original_fields = reader.fieldnames or []

    max_links = max(len(ordered_links(item)) for item in prepared)
    link_fields = [
        field
        for index in range(1, max_links + 1)
        for field in (f"link{index}_label", f"link{index}_url", f"link{index}_color")
    ]
    fields = BASE_FIELDS + link_fields

    audiobook_rows = []
    for item in prepared:
        title = item["lecture"]
        row = {
            "name": title,
            "category": "Audiobooks",
            "language": LANGUAGES[title],
            "publication_date": "",
            "image": f"{IMAGE_BASE_URL}/{IMAGE_FILENAMES[title]}",
            "image_fit": "contain",
            "display_in_purchase": "true",
            "description": item["source_note"],
        }
        for index, link in enumerate(ordered_links(item), start=1):
            retailer = link["retailer"]
            row[f"link{index}_label"] = retailer
            row[f"link{index}_url"] = link["url"]
            row[f"link{index}_color"] = RETAILER_COLORS.get(retailer, "primary")
        audiobook_rows.append(row)

    unknown_fields = set(original_fields) - set(fields)
    if unknown_fields:
        raise ValueError(f"Unsupported existing fields: {sorted(unknown_fields)}")

    insertion_index = next(
        (
            index for index, row in enumerate(existing)
            if row.get("category") == "Applications & Resources"
        ),
        len(existing),
    )
    rows = existing[:insertion_index] + audiobook_rows + existing[insertion_index:]

    with resources_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Imported {len(audiobook_rows)} audiobooks with up to {max_links} retailer links.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kit_dir", type=Path)
    parser.add_argument("--resources-csv", type=Path, default=DEFAULT_RESOURCES_CSV)
    args = parser.parse_args()
    import_resources(args.kit_dir, args.resources_csv)


if __name__ == "__main__":
    main()
