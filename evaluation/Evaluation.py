# evaluation.py
# This file contains the refactored code for the classroom evaluation system.

from class_analyser import ClassroomAnalyzer
import os
from datetime import datetime
import re


class Evaluation:
    """
    Evaluate classroom teaching and generate a comprehensive assessment report.
    Handles the workflow from loading data through generating a report.
    """

    def __init__(self):
        """
        Initialize the evaluator with a ClassroomAnalyzer instance.
        """
        self.analyzer = ClassroomAnalyzer()

    def _auto_select_latest(self):
        """
        Automatically select the latest log directory(YYYYMMDD_HHMMSS),And back (datetime_str, event_id).
        Use the largest numeric subdirectory as the event ID, or 1 if none exists.
        """
        current_dir = os.path.dirname(__file__)
        project_root = os.path.dirname(current_dir)
        logs_root = os.path.join(project_root, "logs")

        if not os.path.isdir(logs_root):
            raise RuntimeError(f"Log root directory does not exist: {logs_root}")

        # Filter Matches YYYYMMDD_HHMMSS Format directories and sort them
        pattern = re.compile(r"^\d{8}_\d{6}$")
        candidates = [d for d in os.listdir(logs_root) if os.path.isdir(os.path.join(logs_root, d)) and pattern.match(d)]
        if not candidates:
            raise RuntimeError(f"No log directory matching YYYYMMDD_HHMMSS was found under {logs_root}")

        candidates.sort()
        latest = candidates[-1]

        # Select Events ID:Take the largest number subdirectories in the log directory; if not, default 1
        latest_path = os.path.join(logs_root, latest)
        event_subdirs = []
        for name in os.listdir(latest_path):
            full = os.path.join(latest_path, name)
            if os.path.isdir(full) and name.isdigit():
                try:
                    event_subdirs.append(int(name))
                except Exception:
                    continue
        event_id = max(event_subdirs) if event_subdirs else 1

        print(f"🕒 No log name specified, latest log automatically selected: {latest}")
        print(f"🧭 Event ID: {event_id}")
        return latest, event_id

    def markdown_to_pdf(self, md_path: str, pdf_path: str = None) -> str:
        """
        Convert a Markdown file to PDF using WeasyPrint or an alternative.

        Args:
            md_path (str): Path to the Markdown file.
            pdf_path (str, optional): Desired path for the output PDF.
                                       If None, the output path is generated automatically.

        Returns:
            str: Path to the generated PDF or fallback HTML file.
                 Return None if all conversion methods fail.
        """
        # If not specified PDF path, generate automatically
        if pdf_path is None:
            pdf_path = md_path.replace('.md', '.pdf')

        # --- Conversion method (ordered by priority)) ---

        # 1. Priority:WeasyPrint
        result = self._convert_with_weasyprint(md_path, pdf_path)
        if result:
            return result

        # 2. Alternative:pdfkit
        result = self._convert_with_pdfkit(md_path, pdf_path)
        if result:
            return result

        # 3. Final Alternative:HTML
        html_path = self._generate_html_fallback(md_path)
        if html_path:
            print(f"📄 Generated fallback HTML file:  {html_path}")
            print("💡 Open the HTML file in a browser and use Print to save it as a PDF.")
            return html_path

        print("❌ All conversion methods failed.")
        return None

    def _convert_with_weasyprint(self, md_path: str, pdf_path: str) -> str:
        """Convert Markdown to PDF with WeasyPrint."""
        try:
            import markdown2
            from weasyprint import HTML, CSS

            print("🔄 Trying to use WeasyPrint Convert...")

            with open(md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            html_content = markdown2.markdown(md_content, extras=['tables', 'fenced-code-blocks', 'header-ids'])

            html_doc = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Assessment of classroom teaching</title>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """

            css_styles = """
            @page {
                size: A4;
                margin: 2cm;
            }

            body {
                font-family: Arial, Helvetica, sans-serif;
                line-height: 1.8;
                color: #333;
                font-size: 14px;
            }

            h1 {
                color: #2c3e50;
                font-size: 24px;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-bottom: 30px;
                page-break-after: avoid;
            }

            h2 {
                color: #34495e;
                font-size: 20px;
                border-bottom: 2px solid #ecf0f1;
                padding-bottom: 8px;
                margin-top: 40px;
                margin-bottom: 20px;
                page-break-after: avoid;
            }

            h3 {
                color: #7f8c8d;
                font-size: 16px;
                margin-top: 30px;
                margin-bottom: 15px;
                page-break-after: avoid;
            }

            p {
                margin-bottom: 15px;
                text-align: justify;
                text-indent: 2em;
            }

            ul, ol {
                margin-left: 20px;
                margin-bottom: 15px;
            }

            li {
                margin-bottom: 8px;
                line-height: 1.6;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                page-break-inside: avoid;
            }

            th, td {
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }

            th {
                background-color: #f8f9fa;
                font-weight: bold;
            }

            code {
                background-color: #f8f8f8;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: "Courier New", monospace;
                font-size: 13px;
            }

            pre {
                background-color: #f8f8f8;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
                margin: 15px 0;
                page-break-inside: avoid;
            }

            blockquote {
                border-left: 4px solid #3498db;
                padding-left: 20px;
                margin: 20px 0;
                font-style: italic;
                color: #666;
            }
            """

            HTML(string=html_doc).write_pdf(
                pdf_path,
                stylesheets=[CSS(string=css_styles)]
            )

            print(f"✅ PDF Conversion succeeded (WeasyPrint): {pdf_path}")
            return pdf_path

        except ImportError:
            print("⚠️ WeasyPrint Not installed.")
            print("💡 Install Command: pip install weasyprint")
            return None
        except Exception as e:
            print(f"⚠️ WeasyPrint Conversion failed: {e}")
            return None

    def _convert_with_pdfkit(self, md_path: str, pdf_path: str) -> str:
        """Convert Markdown to PDF with pdfkit."""
        try:
            import markdown2
            import pdfkit

            print("🔄 Trying to use pdfkit Convert...")

            with open(md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            html_content = markdown2.markdown(md_content, extras=['tables', 'fenced-code-blocks'])

            pdfkit.from_string(html_content, pdf_path)

            print(f"✅ PDF Conversion succeeded (pdfkit): {pdf_path}")
            return pdf_path

        except ImportError:
            print("⚠️ pdfkit Not installed.")
            return None
        except Exception as e:
            print(f"⚠️ pdfkit Conversion failed: {e}")
            return None

    def _generate_html_fallback(self, md_path: str) -> str:
        """Generate an HTML file as a fallback."""
        try:
            import markdown2

            print("🔄 Generating HTML File as Alternative...")

            with open(md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            html_content = markdown2.markdown(md_content, extras=['tables', 'fenced-code-blocks'])

            html_doc = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Assessment of classroom teaching</title>
                <style>
                    body {{
                        font-family: Arial, Helvetica, sans-serif;
                        line-height: 1.8;
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 40px;
                        color: #333;
                    }}
                    h1 {{
                        color: #2c3e50;
                        border-bottom: 3px solid #3498db;
                        padding-bottom: 10px;
                    }}
                    h2 {{
                        color: #34495e;
                        border-bottom: 2px solid #ecf0f1;
                        padding-bottom: 8px;
                        margin-top: 40px;
                    }}
                    h3 {{
                        color: #7f8c8d;
                        margin-top: 30px;
                    }}
                    p {{
                        margin-bottom: 15px;
                        text-align: justify;
                    }}
                    ul, ol {{
                        margin-left: 20px;
                    }}
                    li {{
                        margin-bottom: 8px;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin: 20px 0;
                    }}
                    th, td {{
                        border: 1px solid #ddd;
                        padding: 12px;
                        text-align: left;
                    }}
                    th {{
                        background-color: #f8f9fa;
                    }}
                    @media print {{
                        body {{
                            margin: 0;
                            padding: 20px;
                        }}
                    }}
                </style>
            </head>
            <body>
                {html_content}
                <div style="margin-top: 50px; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
                    <p><strong>💡 Hint:</strong> To Save this page as PDF,Use the browser 's print function:</p>
                    <ul>
                        <li>Press Cmd+P (Mac) or Ctrl+P (Windows)</li>
                        <li>Selection "Save As PDF"</li>
                        <li>Adjust page settings to get the best result</li>
                    </ul>
                </div>
            </body>
            </html>
            """

            html_path = md_path.replace('.md', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_doc)

            return html_path

        except Exception as e:
            print(f"⚠️ HTML Failed to generate: {e}")
            return None

    def run_evaluation(self, datetime_str: str = None, event_id: int = None):
        """
        Run a comprehensive assessment for the specified log timestamp and event ID.

        Args:
            datetime_str (str): Log timestamp, for example '20250804_164319'.
            event_id (int): Event ID.
        """
        print("Assessment system for classroom teaching (Auto-integrated analysis mode)")
        print("=" * 70)

        # Fetch the directory where the current script is(evaluation/)
        current_dir = os.path.dirname(__file__)
        # Get the root directory of the project (i.e evaluation Parent directory)
        project_root = os.path.dirname(current_dir)

        # Automatically select the latest logs and events ID
        if not datetime_str or event_id is None:
            datetime_str, event_id = self._auto_select_latest()

        # Build file path according to input parameter dynamics
        logs_dir = os.path.join(project_root, "logs", datetime_str, str(event_id))
        classroom_file = os.path.join(logs_dir, "output.txt")
        objectives_file = os.path.join(logs_dir, "target.txt")
        student_folder = os.path.join(project_root, "stu_exercises")

        print(f"🔗 Building Path:")
        print(f"  - Classroom log: {classroom_file}")
        print(f"  - Curriculum objectives: {objectives_file}")
        print(f"  - Student results directory: {student_folder}")
        print(f"  - Student result filename pattern: {{student.name}}_exercise_results_{datetime_str}_{event_id}.json")

        if not self.analyzer.load_data_from_folder(classroom_file, student_folder, objectives_file, datetime_str,
                                                   event_id):
            print("Failed to load evaluation data. Exiting.")
            return

        print(f"\n✅ Data loaded successfully!")
        print(f"- Classroom log: Loaded")
        print(f"- Students included: {len(self.analyzer.student_results)}")

        print("\n" + "=" * 70)
        print("Starting the evaluation...")
        print("=" * 70)

        try:
            # First, show your student grades
            print("\n📊 Student performance statistics")
            print("-" * 30)
            self.analyzer.print_student_accuracy()

            # Comprehensive analysis of classroom logs
            print("\n🔍 Classroom log analysis")
            print("-" * 30)
            classroom_analysis = self.analyzer.analyze_classroom_record_comprehensive()

            if "error" in classroom_analysis:
                print(f"Classroom analysis failed: {classroom_analysis['error']}")
            else:
                print("\n" + "=" * 70)
                print("📋 Comprehensive classroom assessment")
                print("=" * 70)
                print(classroom_analysis['comprehensive_analysis'])

                # Autosave As Markdown Documentation
                output_dir = os.path.join(os.path.dirname(__file__), 'analysis_output')
                os.makedirs(output_dir, exist_ok=True)
                # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                # md_path = os.path.join(output_dir, f'analysis_report_{timestamp}.md')
                md_path = os.path.join(output_dir, f'analysis_report_{datetime_str}_{event_id}.md')

                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(f"# Comprehensive classroom assessment\n\n")
                    f.write(f"## Generated: {classroom_analysis.get('timestamp', '')}\n\n")
                    dims = classroom_analysis.get('dimensions', {})
                    for key, value in dims.items():
                        f.write(f"### {key}\n{value}\n\n")
                    f.write(f"## Comprehensive assessment\n{classroom_analysis['comprehensive_analysis']}\n")

                print(f"\n📄 Saved Markdown report: {md_path}")

                # Convert to PDF
                result_path = self.markdown_to_pdf(md_path)
                if result_path and result_path.endswith('.pdf'):
                    print(f"📑 Exported PDF report: {result_path}")
                elif result_path and result_path.endswith('.html'):
                    print(f"📄 Generated HTML report: {result_path}")

        except Exception as e:
            print(f"Error during analysis: {e}")

        print("\n" + "=" * 70)
        print("✅ Analysis complete.")
        print("=" * 70)


if __name__ == "__main__":
    evaluator = Evaluation()
    # Select the latest log directory and event automatically when no arguments are provided.
    evaluator.run_evaluation()
