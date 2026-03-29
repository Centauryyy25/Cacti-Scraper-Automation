"""Progress tracking singleton for pipeline steps."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProgressTracker:
    """Tracks progress of scraping and OCR operations."""
    
    scraping: dict = field(default_factory=lambda: {
        'current': 0,
        'total': 0,
        'status': 'idle',
        'message': 'Ready to start',
        'current_folder': None,
        'start_time': None,
        'usernames_count': 0
    })
    
    ocr: dict = field(default_factory=lambda: {
        'current': 0,
        'total': 0,
        'status': 'idle',
        'message': 'Ready to start',
        'current_file': ''
    })
    
    def reset_scraping(self):
        """Reset scraping progress."""
        self.scraping.update({
            'current': 0,
            'total': 0,
            'status': 'idle',
            'message': 'Ready to start',
            'current_folder': None,
            'start_time': None,
            'usernames_count': 0
        })
    
    def reset_ocr(self):
        """Reset OCR progress."""
        self.ocr.update({
            'current': 0,
            'total': 0,
            'status': 'idle',
            'message': 'Ready to start',
            'current_file': ''
        })
    
    def reset_all(self):
        """Reset all progress."""
        self.reset_scraping()
        self.reset_ocr()


# Singleton instance
progress = ProgressTracker()
