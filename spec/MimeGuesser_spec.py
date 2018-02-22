from parsing import ContentMimeGuesser, ExtensionMimeGuesser
from unittest import TestCase


class MimeGuesserTest(TestCase):

    def test_content_guesser(self):

        guesser = ContentMimeGuesser()

        self.assertEqual("text/x-shellscript", guesser.guess_mime("test_folder/test_utf8.sh"))
        self.assertEqual("text/plain", guesser.guess_mime("test_folder/more_books.json"))
        self.assertEqual("application/java-archive", guesser.guess_mime("test_folder/post.jar"))
        self.assertEqual("image/jpeg", guesser.guess_mime("test_folder/sample_1.jpg"))

    def test_extension_guesser(self):

        guesser = ExtensionMimeGuesser()

        self.assertEqual("text/x-sh", guesser.guess_mime("test_folder/test_utf8.sh"))
        self.assertEqual("application/json", guesser.guess_mime("test_folder/more_books.json"))
        self.assertEqual("application/java-archive", guesser.guess_mime("test_folder/post.jar"))
        self.assertEqual("image/jpeg", guesser.guess_mime("test_folder/sample_1.jpg"))
