import unittest

from youtube.metadata import get_youtube_metadata


class YTMetadata(unittest.TestCase):
    def test_get_video_metadata(self):
        video_url = 'https://www.youtube.com/watch?v=Rg35oYuus-w'
        metadata = get_youtube_metadata(video_url)

        print(metadata)

        self.assertIsNotNone(metadata.title)
        self.assertNotEqual(metadata.title, "")

        self.assertIsNotNone(metadata.full_title)
        self.assertNotEqual(metadata.full_title, "")

        self.assertIsNotNone(metadata.subtitles)

        self.assertIsNotNone(metadata.duration)
        self.assertGreater(metadata.duration, 0)

        self.assertIn('en', metadata.subtitles)
        self.assertNotEqual(metadata.subtitles['en'], {})

        self.assertIsNotNone(metadata.upload_date)
        self.assertIsNotNone(metadata.thumbnail)


if __name__ == '__main__':
    unittest.main()
