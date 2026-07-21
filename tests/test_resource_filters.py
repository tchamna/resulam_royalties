"""Regression tests for URL-driven Resources-tab filtering."""

import unittest

from src.dashboard.public import (
    PublicDashboard,
    matches_resource_filters,
    parse_filter_search_string,
)


class ResourceFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dashboard = PublicDashboard.__new__(PublicDashboard)
        cls.items = [
            item
            for item in dashboard._load_resource_items(purchase_only=False)
            if item.get("category") != "Comics"
        ]

    def matching_names(self, **filters):
        return [
            item["name"]
            for item in self.items
            if matches_resource_filters(item, **filters)
        ]

    def test_duala_audiobooks_url_filters_with_and_semantics(self):
        self.assertEqual(
            self.matching_names(
                selected_language="duala",
                selected_category="audiobooks",
            ),
            ["Duala (Douala) Language Phrasebook"],
        )

    def test_online_courses_author_url_filters_with_and_semantics(self):
        self.assertEqual(
            self.matching_names(
                selected_author="claude lionel mvondo edzoa",
                selected_category="online courses",
            ),
            ["Ewondo Udemy"],
        )

    def test_url_parser_decodes_plus_and_normalizes_case(self):
        context = {
            "years": {2026},
            "languages": {"Duala"},
            "categories": {"Online Courses", "Audiobooks"},
            "books": set(),
            "authors": {"Claude Lionel Mvondo Edzoa"},
            "book_types": {"all"},
            "tabs": {"purchase", "resources"},
            "chart_modes": {"all_stacked"},
        }
        parsed = parse_filter_search_string(
            "?category=online+courses"
            "&author=claude+lionel+mvondo+edzoa"
            "&tab=RESOURCES",
            context,
        )
        self.assertEqual(parsed["category"], "Online Courses")
        self.assertEqual(parsed["author"], "Claude Lionel Mvondo Edzoa")
        self.assertEqual(parsed["tab"], "resources")

    def test_other_official_resource_dimensions(self):
        item = {
            "language": "Ewondo",
            "languages": ["Ewondo", "French"],
            "category": "Online Courses",
            "authors": ["Claude Lionel Mvondo Edzoa", "Shck Tchamna"],
            "book_types": ["Course"],
            "books": ["ewondo_phrasebook"],
            "publication_date": "2026-01",
        }
        self.assertTrue(
            matches_resource_filters(
                item,
                selected_years=[2026],
                selected_language="french",
                selected_author="Claude Lionel Mvondo Edzoa",
                selected_booktype="course",
                selected_book="EWONDO_PHRASEBOOK",
                selected_category="online courses",
            )
        )
        self.assertFalse(matches_resource_filters(item, selected_years=[2025]))


if __name__ == "__main__":
    unittest.main()
