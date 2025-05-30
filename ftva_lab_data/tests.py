from django.test import TestCase
from ftva_lab_data.models import SheetImport
from django.contrib.auth import get_user_model
from ftva_lab_data.views_utils import get_field_value


class GetFieldValueTests(TestCase):
    def setUp(self):
        # Create a test SheetImport object with foreign key relations
        self.user = get_user_model().objects.create_user(username="testuser")
        self.item_with_user = SheetImport.objects.create(
            file_name="test_file", assigned_user=self.user
        )
        self.item_without_user = SheetImport.objects.create(
            file_name="test_file_no_user"
        )

    def test_get_field_value_direct_field(self):
        value = get_field_value(self.item_with_user, "file_name")
        self.assertEqual(value, "test_file")

    def test_get_field_value_foreign_key_field(self):
        # Test foreign key field access
        value = get_field_value(self.item_with_user, "assigned_user__username")
        self.assertEqual(value, "testuser")

    def test_get_field_value_non_existent_field(self):
        # Test non-existent field access
        value = get_field_value(self.item_with_user, "non_existent_field")
        self.assertEqual(value, "")

    def test_get_field_value_empty_string(self):
        # Test empty string field access
        value = get_field_value(self.item_without_user, "assigned_user__username")
        self.assertEqual(value, "")
