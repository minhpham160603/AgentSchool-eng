# classroom_analyzer.py
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import pandas as pd
import os
import glob
from typing import Dict, List, Tuple
from datetime import datetime
import asyncio
from util.model import call_LLM


class ClassroomAnalyzer:
    """Classroom records and student achievement analyser"""
    
    def __init__(self):
        self.classroom_data = None
        self.student_results = {}
        self.analysis_results = {}
        self.course_objectives = None  # Store course objectives
    
    def load_course_objectives(self, objectives_file: str):
        """Load a course objectives document."""
        try:
            with open(objectives_file, 'r', encoding='utf-8') as f:
                self.course_objectives = f.read()
            print(f"Loaded course objectives: {objectives_file}")
            return True
        except Exception as e:
            print(f"Failed to load course objectives: {e}")
            return False

    def load_data_from_folder(self, classroom_file: str, student_folder: str, objectives_file: str = None,
                              datetime_str: str = None, integer_id: int = None):
        """
        Load classroom records, student achievement data and course goals from folders.
        Use datetime_str and integer_id to find the matching student result files.
        """
        # Load class records
        try:
            with open(classroom_file, 'r', encoding='utf-8') as f:
                self.classroom_data = f.read()
            print(f"Loaded classroom records: {classroom_file}")
        except Exception as e:
            print(f"Failed to load classroom records: {e}")
            return False

        # Load course objectives when provided.
        if objectives_file:
            if not self.load_course_objectives(objectives_file):
                return False

        # Load student record
        if datetime_str and integer_id is not None:
            # student_folder = os.path.join(student_base_folder, datetime_str, str(integer_id))
            print(f"Looking for student scores in: {student_folder}")

            # Adjust the file search mode to match the new format
            pattern = os.path.join(student_folder, f"*_exercise_results_{datetime_str}_{integer_id}.json")
            student_files = glob.glob(pattern)

            if not student_files:
                print(f"❌ No matching student score files found:{pattern}")
                return False

            # Suppose you have a way to load these files
            self._load_student_files(student_files)

        return True

    def load_student_data_from_folder(self, student_folder: str):
        """Load student results from a folder."""
        student_files = self._get_student_files(student_folder)
        
        if not student_files:
            print(f"No student records found in {student_folder}")
            return False
        
        print(f"Found {len(student_files)} student result files")
        for file in student_files:
            print(f"  - {os.path.basename(file)}")
        
        return self._load_student_files(student_files)

    def _get_student_files(self, folder_path):
        """Find student result files in the given folder."""
        if not os.path.exists(folder_path):
            print(f"Student results directory not found: {folder_path}")
            return []

        # Find All JSON File and filter out files that match the new naming pattern
        pattern = os.path.join(folder_path, "*_exercise_results_*.json")
        files = glob.glob(pattern)

        # Sort By File Name
        files.sort()
        return files

    def _load_student_files(self, student_files: List[str]):
        """Load student record"""
        for file_path in student_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    student_data = json.load(f)

                # The name of the student is taken from the file name, which is assumed to be the first part
                file_name = os.path.basename(file_path)
                student_name = file_name.split('_')[0]
                # Only load the subject details, the command number becomes the top key, which is consistent with statistical logic
                self.student_results[student_name] = student_data.get("detailed_answers", {})
                print(f"Student achievement has been successfully loaded: {student_name}")

            except Exception as e:
                print(f"Failed to load student grades {file_path}: {e}")

        return len(self.student_results) > 0

    
    def _truncate_classroom_data(self, max_chars: int = 30000) -> str:
        """Truncate classroom records to fit model input limits."""
        if not self.classroom_data:
            return ""
        
        if len(self.classroom_data) <= max_chars:
            return self.classroom_data
        
        # Truncate the text and append a notice.
        truncated = self.classroom_data[:max_chars]
        truncated += f"\n\n[Note: The original document is too long and has been cut to {max_chars} characters for analysis]"
        return truncated
    
    def calculate_student_accuracy(self) -> Dict:
        """Calculate the correct rate per student"""
        if not self.student_results:
            return {"error": "Student achievement data not loaded"}
        
        results = {
            "individual_accuracy": {},
            "overall_accuracy": 0.0,
            "total_students": len(self.student_results)
        }
        
        # Collect all question numbers.
        all_questions = set()
        for student_data in self.student_results.values():
            if isinstance(student_data, dict):
                all_questions.update(student_data.keys())
        
        # Keep numeric question identifiers.
        numeric_questions = []
        for q in all_questions:
            try:
                numeric_questions.append(int(q))
            except (ValueError, TypeError):
                continue
        
        numeric_questions.sort()
        
        if not numeric_questions:
            return {"error": "No valid question data found"}
        
        total_correct = 0
        total_attempts = 0
        
        # Calculate the correct rate per student
        for student_name, student_data in self.student_results.items():
            if not isinstance(student_data, dict):
                continue
                
            correct = 0
            answered = 0
            
            for question_num in numeric_questions:
                question_str = str(question_num)
                if question_str in student_data:
                    answered += 1
                    question_data = student_data[question_str]
                    
                    if isinstance(question_data, dict):
                        is_correct = question_data.get("correct", False)
                    else:
                        is_correct = question_data
                    
                    if is_correct is True or is_correct == 1 or is_correct == "correct" or is_correct == "1":
                        correct += 1
            
            accuracy = round((correct / answered) * 100, 1) if answered > 0 else 0
            
            results["individual_accuracy"][student_name] = {
                "correct": correct,
                "total": answered,
                "accuracy": accuracy
            }
            
            total_correct += correct
            total_attempts += answered
        
        # Calculate overall correct rate
        results["overall_accuracy"] = round((total_correct / total_attempts) * 100, 1) if total_attempts > 0 else 0
        
        return results

    def print_student_accuracy(self):
        """Print student correctness statistics"""
        results = self.calculate_student_accuracy()
        if "error" in results:
            print(f"Statistics Failed: {results['error']}")
            return results
        
        print(f"\n📊 Statistics on student performance")
        print(f"- Students included: {results['total_students']}")
        print(f"- Average class accuracy: {results['overall_accuracy']}%")
        
        print(f"\n👥 Accuracy per student:")
        for student_name, data in results["individual_accuracy"].items():
            print(f"- {student_name}: {data['correct']}/{data['total']} ({data['accuracy']}%)")
        
        return results

    def analyze_teaching_content(self) -> Dict:
        """Analysis of teaching content"""
        if not self.classroom_data:
            return {"error": "Classroom records not loaded"}
        
        truncated_data = self._truncate_classroom_data()
        
        content_prompt = """
Analyze the following classroom records in English. Focus on:

### Teaching content
- Main topics and concepts taught
- Teaching methods and strategies
- Types of classroom activities

Provide a detailed, evidence-based analysis. Write the entire response in English.
        """
        
        try:
            # response = self.client.chat.completions.create(
            #     model="deepseek-chat",
            #     messages=[
            #         {"role": "system", "content": "You're a senior education specialist. You're good at analysing teaching content and methods."},
            #         {"role": "user", "content": f"{content_prompt}\n\n Classroom records:\n{truncated_data}"}
            #     ],
            #     temperature=0.1,
            #     max_tokens=800
            # )
            #
            # return {
            #     "dimension": "teaching_content",
            #     "analysis": response.choices[0].message.content,
            #     "timestamp": datetime.now().isoformat()
            # }
            messages=[
                {"role": "system", "content": "You are an experienced education specialist. Analyze teaching content and methods, and respond entirely in English."},
                {"role": "user", "content": f"{content_prompt}\n\n Classroom records:\n{truncated_data}"}
            ]
            response = asyncio.run(call_LLM("evaluation", messages))
            return {
                "dimension": "teaching_content",
                "analysis": response,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Teaching content analysis failed: {str(e)}"}

    def analyze_student_engagement(self) -> Dict:
        """Analysis of student participation"""
        if not self.classroom_data:
            return {"error": "Classroom records not loaded"}
        
        truncated_data = self._truncate_classroom_data()
        
        engagement_prompt = """
Analyze student participation in the following classroom records. Focus on:

### Student participation
- Frequency and quality of student interaction
- Student questions and answers
- Student attention and engagement

Provide a detailed, evidence-based analysis. Write the entire response in English.
        """
        
        try:
            # response = self.client.chat.completions.create(
            #     model="deepseek-chat",
            #     messages=[
            #         {"role": "system", "content": "You're a senior education specialist who's good at observing and analysing student classroom participation."},
            #         {"role": "user", "content": f"{engagement_prompt}\n\n Classroom records:\n{truncated_data}"}
            #     ],
            #     temperature=0.1,
            #     max_tokens=800
            # )
            #
            # return {
            #     "dimension": "student_engagement",
            #     "analysis": response.choices[0].message.content,
            #     "timestamp": datetime.now().isoformat()
            # }
            messages=[
                {"role": "system", "content": "You are an experienced education specialist. Analyze student participation in class, and respond entirely in English."},
                {"role": "user", "content": f"{engagement_prompt}\n\n Classroom records:\n{truncated_data}"}
            ]
            response = asyncio.run(call_LLM("evaluation", messages))

            return {
                "dimension": "student_engagement",
                "analysis": response,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {"error": f"Student participation analysis failed: {str(e)}"}

    def analyze_teaching_effectiveness(self) -> Dict:
        """Analysis of teaching results"""
        if not self.classroom_data:
            return {"error": "Classroom records not loaded"}
        
        truncated_data = self._truncate_classroom_data()
        
        effectiveness_prompt = """
Analyze the teaching effectiveness shown in the following classroom records. Focus on:

### Teaching effectiveness
- Clarity of explanations and knowledge presentation
- Evidence of student understanding
- Progress toward the lesson objectives

Provide a detailed, evidence-based analysis. Write the entire response in English.
        """
        
        try:
            # response = self.client.chat.completions.create(
            #     model="deepseek-chat",
            #     messages=[
            #         {"role": "system", "content": "You're a senior education assessor. You're good at evaluating performance and learning outcomes."},
            #         {"role": "user", "content": f"{effectiveness_prompt}\n\n Classroom records:\n{truncated_data}"}
            #     ],
            #     temperature=0.1,
            #     max_tokens=800
            # )
            #
            # return {
            #     "dimension": "teaching_effectiveness",
            #     "analysis": response.choices[0].message.content,
            #     "timestamp": datetime.now().isoformat()
            # }
            messages=[
                {"role": "system", "content": "You are an experienced education assessor. Evaluate student performance and learning outcomes, and respond entirely in English."},
                {"role": "user", "content": f"{effectiveness_prompt}\n\n Classroom records:\n{truncated_data}"}
            ]
            response = asyncio.run(call_LLM("evaluation", messages))

            return {
                "dimension": "teaching_effectiveness",
                "analysis": response,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {"error": f"Teaching effects analysis failed: {str(e)}"}

    def analyze_classroom_atmosphere(self) -> Dict:
        """Analysis of classroom atmosphere"""
        if not self.classroom_data:
            return {"error": "Classroom records not loaded"}
        
        truncated_data = self._truncate_classroom_data()
        
        atmosphere_prompt = """
Analyze the classroom climate shown in the following classroom records. Focus on:

### Classroom climate
- Quality of teacher-student interaction
- Classroom routines and behavior
- Signs of a supportive, engaged learning environment

Provide a detailed, evidence-based analysis. Write the entire response in English.
        """
        
        try:
            # response = self.client.chat.completions.create(
            #     model="deepseek-chat",
            #     messages=[
            #         {"role": "system", "content": "You're an expert in classroom observation."},
            #         {"role": "user", "content": f"{atmosphere_prompt}\n\n Classroom records:\n{truncated_data}"}
            #     ],
            #     temperature=0.1,
            #     max_tokens=800
            # )
            #
            # return {
            #     "dimension": "classroom_atmosphere",
            #     "analysis": response.choices[0].message.content,
            #     "timestamp": datetime.now().isoformat()
            # }
            messages=[
                {"role": "system", "content": "You are an experienced classroom observer. Analyze the classroom climate and respond entirely in English."},
                {"role": "user", "content": f"{atmosphere_prompt}\n\n Classroom records:\n{truncated_data}"}
            ]
            response = asyncio.run(call_LLM("evaluation", messages))

            return {
                "dimension": "classroom_atmosphere",
                "analysis": response,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Classroom atmosphere analysis failed: {str(e)}"}

    def generate_improvement_suggestions(self) -> Dict:
        """Generate recommendations for improvement"""
        if not self.classroom_data:
            return {"error": "Classroom records not loaded"}
        
        truncated_data = self._truncate_classroom_data()
        
        suggestions_prompt = """
Based on the following classroom records, recommend practical improvements. Focus on:

### Recommendations
- Ways to strengthen teaching methods
- Strategies to increase student participation
- Classroom management improvements

Make each recommendation concrete and relevant to the evidence. Write the entire response in English.
        """
        
        try:
            # response = self.client.chat.completions.create(
            #     model="deepseek-chat",
            #     messages=[
            #         {"role": "system", "content": "You're a senior educational adviser who's good at providing teachers with practical suggestions for improvement."},
            #         {"role": "user", "content": f"{suggestions_prompt}\n\n Classroom records:\n{truncated_data}"}
            #     ],
            #     temperature=0.1,
            #     max_tokens=800
            # )
            #
            # return {
            #     "dimension": "improvement_suggestions",
            #     "analysis": response.choices[0].message.content,
            #     "timestamp": datetime.now().isoformat()
            # }
            messages=[
                {"role": "system", "content": "You are an experienced educational adviser. Give teachers practical suggestions for improvement, and respond entirely in English."},
                {"role": "user", "content": f"{suggestions_prompt}\n\n Classroom records:\n{truncated_data}"}
            ]
            response = asyncio.run(call_LLM("evaluation", messages))

            return {
                "dimension": "improvement_suggestions",
                "analysis": response,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {"error": f"Improvement proposal generation failed: {str(e)}"}

    def analyze_classroom_record_comprehensive(self) -> Dict:
        """Comprehensive analysis of classroom records - Call all dimensions and generate synthesis reports"""
        if not self.classroom_data:
            return {"error": "Classroom records not loaded"}
        
        print("The dimensions are being analysed...")
        
        # Analytic function calling each dimension
        dimensions_results = {}
        
        # 1. Analysis of teaching content
        print("- Analysis of teaching content...")
        content_result = self.analyze_teaching_content()
        if "error" not in content_result:
            dimensions_results["teaching_content"] = content_result["analysis"]
        
        # 2. Student participation analysis
        print("- Student participation analysis...")
        engagement_result = self.analyze_student_engagement()
        if "error" not in engagement_result:
            dimensions_results["student_engagement"] = engagement_result["analysis"]
        
        # 3. Assessment of the effectiveness of teaching
        print("- Assessment of the effectiveness of teaching...")
        effectiveness_result = self.analyze_teaching_effectiveness()
        if "error" not in effectiveness_result:
            dimensions_results["teaching_effectiveness"] = effectiveness_result["analysis"]
        
        # 4. Classroom atmosphere analysis
        print("- Classroom atmosphere analysis...")
        atmosphere_result = self.analyze_classroom_atmosphere()
        if "error" not in atmosphere_result:
            dimensions_results["classroom_atmosphere"] = atmosphere_result["analysis"]
        
        # 5. Suggested improvements
        print("- Generating improvement recommendations...")
        suggestions_result = self.generate_improvement_suggestions()
        if "error" not in suggestions_result:
            dimensions_results["improvement_suggestions"] = suggestions_result["analysis"]
        
        # Generate synthesis reports
        print("- Generating the comprehensive report...")
        comprehensive_analysis = self._generate_comprehensive_report(dimensions_results)
        
        # Save Results
        result = {
            "comprehensive_analysis": comprehensive_analysis,
            "dimensions": dimensions_results,
            "timestamp": datetime.now().isoformat()
        }
        
        self.analysis_results['classroom'] = result
        return result

    def _generate_comprehensive_report(self, dimensions_results: Dict) -> str:
        """Production of synthesis reports based on the results of the analysis of dimensions"""
        if not dimensions_results:
            return "Could not generate synthesis report: lack of dimension analysis"
        
        # Access to detailed student achievement data
        accuracy_results = self.calculate_student_accuracy()
        
        if 'error' in accuracy_results:
            # If data on accomplishments fail to be obtained, the report is still generated without performance information
            overall_accuracy = "Unable to access"
            total_students = "Unknown"
            student_performance_summary = "Failed to obtain student achievement data"
        else:
            overall_accuracy = accuracy_results['overall_accuracy']
            total_students = accuracy_results['total_students']
            
            # Generate student performance summaries
            individual_scores = []
            for student_name, data in accuracy_results['individual_accuracy'].items():
                individual_scores.append(f"{student_name}: {data['accuracy']}%")
            
            student_performance_summary = f"""
Overall class performance:
- Class average accuracy:{overall_accuracy}%
- Participating students: {total_students}
- Individual accuracy:{', '.join(individual_scores)}
            """
        
        # Processing course target information
        if self.course_objectives:
            course_objectives_section = f"""
## Course objectives
{self.course_objectives}
            """
            objectives_analysis_instruction = f"Assess progress toward the course objectives, taking the class average accuracy of {overall_accuracy}% into account."
        else:
            course_objectives_section = "\n## Course objectives\n Course target documents not available"
            objectives_analysis_instruction = "No course objectives were provided. Infer likely objectives from the classroom content and assess progress toward them."
        
        # Build a comprehensive analytical hint
        dimensions_summary = ""
        for dimension, analysis in dimensions_results.items():
            dimension_name = {
                "teaching_content": "Analysis of teaching content",
                "student_engagement": "Student participation analysis",
                "teaching_effectiveness": "Assessment of the effectiveness of teaching",
                "classroom_atmosphere": "Classroom atmosphere analysis",
                "improvement_suggestions": "Suggested improvements"
            }.get(dimension, dimension)
            
            dimensions_summary += f"\n### {dimension_name}\n{analysis}\n"
        
        comprehensive_prompt = f"""
Write a comprehensive classroom assessment in English, drawing on the analyses below, student performance data, and curriculum objectives.

## Dimension analysis
{dimensions_summary}

## Student performance
{student_performance_summary}

{course_objectives_section}

Address all of the following:
1. Overall teaching quality and student performance, including the class average accuracy of {overall_accuracy}%.
2. Student participation and teacher-student interaction.
3. Progress toward the curriculum objectives ({objectives_analysis_instruction}).
4. Key strengths and effective practices.
5. Areas for improvement.
6. Practical recommendations and a concise conclusion.

Use a professional, objective tone. Support conclusions with evidence from the classroom record and connect student learning outcomes to the teaching process and stated curriculum objectives. Write the entire report in English.
        """
        
        try:
            # response = self.client.chat.completions.create(
            #     model="deepseek-chat",
            #     messages=[
            #         {"role": "system", "content": "You are a senior education assessment specialist who is good at conducting a comprehensive analysis of the quality of teaching in the classroom, student learning outcomes and the achievement of curriculum goals, and providing professional evaluation reports."},
            #         {"role": "user", "content": comprehensive_prompt}
            #     ],
            #     temperature=0.1,
            #     max_tokens=1500  # Increase token Number to accommodate more detailed analysis
            # )
            #
            # return response.choices[0].message.content
            messages=[
                {"role": "system",
                 "content": "You are an experienced education assessment specialist. Assess classroom teaching quality, student learning outcomes, and progress toward curriculum objectives, and write professional reports in English."},
                {"role": "user", "content": comprehensive_prompt}
            ]
            response = asyncio.run(call_LLM("evaluation", messages))

            return response

        except Exception as e:
            return f"Failed to generate synthesis report: {str(e)}"
