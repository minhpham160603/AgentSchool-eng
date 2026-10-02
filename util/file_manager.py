"""
File Management Tool Category
For integrated management SchoolAgent Documentation and organization of the project
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

class SchoolAgentFileManager:
    """
    SchoolAgent File Manager for the project
    Provide uniform document preservation, organization and indexing functions
    """
    
    def __init__(self, base_dir: str = "results"):
        """
        Initialise File Manager
        
        Args:
            base_dir: Basic Save Directory
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        # Define Folder Structure
        self.folder_structure = {
            "exercises": "Practice results",
            "memory_analysis": "Memory analysis reports",
            "evaluations": "Findings",
            "progress": "Progress record",
            "logs": "Run Log",
            "backups": "Backup Files",
            "visualizations": "Visualized data"
        }
    
    def get_student_dir(self, student_name: str, date: Optional[datetime] = None) -> Path:
        """
        Retrieving student directory path
        
        Args:
            student_name: Student name
            date: Date, default for today
            
        Returns:
            Student Directory Path
        """
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime("%Y-%m-%d")
        student_dir = self.base_dir / student_name / date_str
        student_dir.mkdir(parents=True, exist_ok=True)
        
        return student_dir
    
    def get_category_dir(self, student_name: str, category: str, date: Optional[datetime] = None) -> Path:
        """
        Path to acquiring a specific category of directory
        
        Args:
            student_name: Student name
            category: File category
            date: Date, default for today
            
        Returns:
            Category Directory Path
        """
        student_dir = self.get_student_dir(student_name, date)
        category_dir = student_dir / category
        category_dir.mkdir(exist_ok=True)
        
        return category_dir
    
    def generate_unique_filename(self, student_name: str, file_type: str, 
                                postfix: str = "", extension: str = ".json") -> str:
        """
        Generate a unique filename (avoid overwrite))
        
        Args:
            student_name: Student name
            file_type: File type
            postfix: Postfix Identification
            extension: File Extension
            
        Returns:
            Only filename
        """
        timestamp = datetime.now().strftime("%H%M%S")
        
        # Build filename
        name_parts = [student_name, file_type]
        if postfix:
            name_parts.append(postfix)
        name_parts.append(timestamp)
        
        filename = "_".join(name_parts) + extension
        return filename
    
    def save_exercise_results(self, student_name: str, data: Dict[Any, Any], 
                            postfix: str = "") -> Path:
        """
        Save the result of the exercise
        
        Args:
            student_name: Student name
            data: Data to save
            postfix: File suffix identifier
            
        Returns:
            File Path to Save
        """
        # Get Save Directory
        save_dir = self.get_category_dir(student_name, "exercises")
        
        # Generate File Name
        filename = self.generate_unique_filename(student_name, "exercise_results", postfix)
        filepath = save_dir / filename
        
        # Add metadata
        enhanced_data = {
            "metadata": {
                "file_info": {
                    "creation_time": datetime.now().isoformat(),
                    "file_version": "2.0",
                    "file_type": "exercise_results",
                    "student_name": student_name,
                    "session_id": f"{student_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                },
                "file_structure": {
                    "relative_path": str(filepath.relative_to(self.base_dir)),
                    "category": "exercises",
                    "backup_available": False
                }
            },
            "data": data
        }
        
        # Save File
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(enhanced_data, f, ensure_ascii=False, indent=4)
        
        # Update Index
        self._update_file_index(student_name, "exercises", filename, enhanced_data["metadata"])
        
        # Create Backup (if needed))
        if self._should_create_backup(filepath):
            self._create_backup(filepath, student_name)
        
        return filepath
    
    def save_memory_analysis(self, student_name: str, data: Dict[Any, Any], 
                           postfix: str = "") -> Path:
        """
        Save memory analysis results
        
        Args:
            student_name: Student name
            data: Data to save
            postfix: File suffix identifier
            
        Returns:
            File Path to Save
        """
        save_dir = self.get_category_dir(student_name, "memory_analysis")
        filename = self.generate_unique_filename(student_name, "memory_analysis", postfix)
        filepath = save_dir / filename
        
        # Add metadata
        enhanced_data = {
            "metadata": {
                "analysis_info": {
                    "creation_time": datetime.now().isoformat(),
                    "analysis_type": "memory_usage_comprehensive",
                    "student_name": student_name,
                    "version": "2.0"
                }
            },
            "analysis": data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(enhanced_data, f, ensure_ascii=False, indent=4)
        
        self._update_file_index(student_name, "memory_analysis", filename, enhanced_data["metadata"])
        
        return filepath
    
    def save_progress_checkpoint(self, student_name: str, data: Dict[Any, Any], 
                               checkpoint_id: str) -> Path:
        """
        Save Progress Checkpoint
        
        Args:
            student_name: Student name
            data: Data to save
            checkpoint_id: Checkpoint Identification
            
        Returns:
            File Path to Save
        """
        save_dir = self.get_category_dir(student_name, "progress")
        filename = self.generate_unique_filename(student_name, "progress", checkpoint_id)
        filepath = save_dir / filename
        
        checkpoint_data = {
            "checkpoint_info": {
                "timestamp": datetime.now().isoformat(),
                "checkpoint_id": checkpoint_id,
                "student_name": student_name,
                "auto_recovery": True
            },
            "progress_data": data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=4)
        
        return filepath
    
    def get_latest_file(self, student_name: str, category: str, 
                       date: Optional[datetime] = None) -> Optional[Path]:
        """
        Get an updated file
        
        Args:
            student_name: Student name
            category: File category
            date: Date, default for today
            
        Returns:
            Path to the latest file, return if no file is available None
        """
        category_dir = self.get_category_dir(student_name, category, date)
        
        if not category_dir.exists():
            return None
        
        # Get all files and sort them by change time
        files = [f for f in category_dir.iterdir() if f.is_file() and f.suffix == '.json']
        if not files:
            return None
        
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        return latest_file
    
    def list_student_sessions(self, student_name: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Lists recent sessions of students
        
        Args:
            student_name: Student name
            days: Check the records of the last few days
            
        Returns:
            Session Record List
        """
        sessions = []
        student_base_dir = self.base_dir / student_name
        
        if not student_base_dir.exists():
            return sessions
        
        # The directories of the last few days
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            date_dir = student_base_dir / date_str
            
            if date_dir.exists():
                index_file = date_dir / "index.json"
                if index_file.exists():
                    with open(index_file, 'r', encoding='utf-8') as f:
                        index_data = json.load(f)
                        sessions.extend(index_data.get("sessions", []))
        
        return sorted(sessions, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    def create_daily_summary(self, student_name: str, date: Optional[datetime] = None) -> Path:
        """
        Create daily summary report
        
        Args:
            student_name: Student name
            date: Date, default for today
            
        Returns:
            Path to summary report document
        """
        if date is None:
            date = datetime.now()
        
        student_dir = self.get_student_dir(student_name, date)
        summary_file = student_dir / f"daily_summary_{date.strftime('%Y%m%d')}.json"
        
        # Collect all activities of the day
        daily_activities = {
            "date": date.strftime("%Y-%m-%d"),
            "student_name": student_name,
            "summary": {
                "exercises_completed": 0,
                "analysis_reports": 0,
                "progress_checkpoints": 0,
                "total_files": 0
            },
            "file_list": [],
            "performance_highlights": []
        }
        
        # Statistical documents
        for category in self.folder_structure.keys():
            category_dir = student_dir / category
            if category_dir.exists():
                files = list(category_dir.glob("*.json"))
                daily_activities["summary"][f"{category}_count"] = len(files)
                daily_activities["file_list"].extend([
                    {
                        "category": category,
                        "filename": f.name,
                        "size_kb": round(f.stat().st_size / 1024, 2),
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    }
                    for f in files
                ])
        
        daily_activities["summary"]["total_files"] = len(daily_activities["file_list"])
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(daily_activities, f, ensure_ascii=False, indent=4)
        
        return summary_file
    
    def _update_file_index(self, student_name: str, category: str, 
                          filename: str, metadata: Dict[str, Any]) -> None:
        """
        Update File Index
        
        Args:
            student_name: Student name
            category: File category
            filename: Filename
            metadata: Metadata
        """
        student_dir = self.get_student_dir(student_name)
        index_file = student_dir / "index.json"
        
        # Read or create an index
        if index_file.exists():
            with open(index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
        else:
            index = {
                "student_name": student_name,
                "created": datetime.now().isoformat(),
                "sessions": []
            }
        
        # Add New Record
        session_record = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "filename": filename,
            "metadata": metadata
        }
        
        index["sessions"].append(session_record)
        
        # Keep Recent 50 Notes
        if len(index["sessions"]) > 50:
            index["sessions"] = index["sessions"][-50:]
        
        # Save Index
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    
    def _should_create_backup(self, filepath: Path) -> bool:
        """
        Judge whether to create backup
        
        Args:
            filepath: File Path
            
        Returns:
            Do you need backup?
        """
        # Greater than 1MB File Create Backup
        file_size_mb = filepath.stat().st_size / (1024 * 1024)
        return file_size_mb > 1.0
    
    def _create_backup(self, filepath: Path, student_name: str) -> None:
        """
        Create File Backup
        
        Args:
            filepath: Source path
            student_name: Student name
        """
        backup_dir = self.get_category_dir(student_name, "backups")
        backup_filename = f"backup_{filepath.stem}_{datetime.now().strftime('%H%M%S')}{filepath.suffix}"
        backup_path = backup_dir / backup_filename
        
        # Copy File
        import shutil
        shutil.copy2(filepath, backup_path)
        
        print(f"📦 Created Backup: {backup_path}")
    
    def cleanup_old_files(self, student_name: str, days_to_keep: int = 30) -> None:
        """
        Clear old files
        
        Args:
            student_name: Student name
            days_to_keep: Number of days retained
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        student_base_dir = self.base_dir / student_name
        
        if not student_base_dir.exists():
            return
        
        # Through Date Directory
        for date_dir in student_base_dir.iterdir():
            if date_dir.is_dir() and date_dir.name != "backups":
                try:
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        # Move to Backup Directory instead of Delete
                        backup_dir = self.get_category_dir(student_name, "backups")
                        archive_name = f"archived_{date_dir.name}_{datetime.now().strftime('%H%M%S')}"
                        import shutil
                        shutil.move(str(date_dir), str(backup_dir / archive_name))
                        print(f"🗄️ Archived old directories: {date_dir.name}")
                except ValueError:
                    # Not a directory in date format, skip
                    continue


# Examples of global file manager
file_manager = SchoolAgentFileManager()


def get_file_manager() -> SchoolAgentFileManager:
    """Fetch global file manager instance"""
    return file_manager
