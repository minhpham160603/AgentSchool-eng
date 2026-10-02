import os
import tiktoken
import json
import sys
import time
import re
import asyncio
import aiofiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
script_dir = os.path.dirname(os.path.abspath(__file__))
from util.model import call_LLM_sync, call_LLM

def count_tokens(text, model="deepseek-reasoner"):
    """Calculate text token Number"""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        #Use cl100k_base As backup
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

async def textbook_pretreat(textbook_file: str = None):
    # Enter and output files
    text_book_file = ""
    if textbook_file:
        text_book_file = textbook_file
    else:
        raise ValueError("Please provide a path to the teaching materials document")
    textbook_refined_file = f"{script_dir}/textbook_refined.txt"
    sections_output_file = f"{script_dir}/sections.json"

    MAX_TOKENS = 20000  # Lower token Limit, avoid interruption of response

    if not os.path.exists(text_book_file):
        raise FileNotFoundError(f"textbook file '{text_book_file}' does not exist")

    with open(text_book_file, 'r', encoding='utf-8') as input_file:
        content = input_file.read()

    token_count = count_tokens(content)
    print(f"Input document token count: {token_count}")  # Display the token count.

    if token_count > MAX_TOKENS:
        print(f"Input is too long; processing it in asynchronous chunks...")
        # Process the material in chunks.
        return await textbook_pretreat_chunked_async(text_book_file, MAX_TOKENS)

    # Prompt with strict JSON requirements.
    prompt = """
    You are an assistant that prepares textbook material in Markdown. Return strict JSON with exactly two fields: "refined_content" (a string) and "pck" (an array of concise strings).

    For refined_content:
    1. Convert formulas to readable plain text while preserving their mathematical meaning.
    2. Remove image links and non-content headers or footers.
    3. Remove exercises while retaining worked examples.
    4. Correct obvious layout and symbol errors, but otherwise preserve the source meaning and sequence.
    5. Insert the exact separator "xiaojiefenge" only at subsection boundaries. Do not add, remove, or reorder lesson sections or paragraphs.
    6. Write all prose in clear, natural English. Preserve formulas, numbers, units, and named entities accurately.

    For pck, identify the subject knowledge in the refined material and summarize each knowledge point in one concise English sentence. Include key concepts, definitions, laws, formulas, relationships, and applications. Return each point as an array item.

    Return valid JSON only. Do not include comments, Markdown fences, or explanatory text outside the JSON object. Escape quotation marks inside JSON strings correctly.
    """

    print("Starting textbook preprocessing (refinement, summary, and subsection extraction)...")
    start_time = time.perf_counter()  # Record start time

    try:
        response = call_LLM_sync(
            "textbook",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content},
            ],
            response_format={'type': 'json_object'}
        )

        end_time = time.perf_counter()  # End of record
        print(f"LLM processing time: {end_time - start_time:.2f} seconds")
        print(f"Response length: {len(response)} characters")  # Show response length

        response_file = f"{script_dir}/raw_response.json"
        refined_file = f"{script_dir}/textbook_refined.txt"
        pck_file = f"{script_dir}/pck.json"
        sections_file = f"{script_dir}/sections.json"

        response_json = {}
        with open(response_file, 'w', encoding='utf-8') as f:
            f.write(response)
        with open(response_file, 'r', encoding='utf-8') as f:
            response_json = json.load(f)

        refined_content = response_json.get("refined_content", "")
        with open(refined_file, 'w', encoding='utf-8') as f:
            f.write(refined_content)
        print(f"Refined content saved to: {refined_file}")

        pck = response_json.get("pck", [])
        with open(pck_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps({"pck": pck}, ensure_ascii=False, indent=2))
        print(f"PCK saved to: {pck_file}")

        #Split the refined content at subsection separators.
        sections = refined_content.split("xiaojiefenge")
        with open(sections_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps({"sections": sections}, ensure_ascii=False, indent=2))
        print(f"Sections saved to: {sections_file}")

        return True
    except Exception as e:
        print(f"Processing error: {e}")
        return False

async def process_chunk_async(chunk, chunk_index):
    """Process one textbook chunk asynchronously."""
    simplified_prompt = """
    Prepare this textbook chunk in Markdown. Return strict JSON with exactly two fields: "refined_content" (a string) and "pck" (an array of concise strings).

    In refined_content, preserve the lesson meaning, formulas, numbers, units, examples, and original sequence. Remove image links, tables of contents, non-content headers and footers, and exercises, while retaining worked examples. Correct obvious layout and symbol errors. Write prose in clear, natural English. Insert the exact separator "xiaojiefenge" only where a subsection begins; do not treat paragraphs or individual knowledge points as subsections.

    In pck, summarize the chunk's key subject concepts, definitions, laws, formulas, relationships, and applications, using one concise English sentence per item.

    Return valid JSON only, with no Markdown fences or text outside the object. Escape quotation marks inside JSON strings correctly.
    """

    try:
        print(f"Starting asynchronous processing of chunk {chunk_index + 1} ...")
        start_time = time.perf_counter()

        # Call the language model for this chunk.
        response = await call_LLM(
            "textbook",
            messages=[
                {"role": "system", "content": simplified_prompt},
                {"role": "user", "content": chunk},
            ],
            response_format={'type': 'json_object'}
        )

        end_time = time.perf_counter()
        print(f"Finished processing chunk {chunk_index + 1} in: {end_time - start_time:.2f} seconds")

        response_json = json.loads(response)
        return {
            "chunk_index": chunk_index,
            "refined_content": response_json.get("refined_content", ""),
            "pck": response_json.get("pck", [])
        }

    except Exception as e:
        print(f"Error processing chunk {chunk_index + 1} asynchronously: {e}")
        return {
            "chunk_index": chunk_index,
            "refined_content": "",
            "pck": []
        }

async def textbook_pretreat_chunked_async(text_book_file, max_tokens, max_concurrent=3):
    """Process a large textbook in chunks."""
    # Read the source file.
    async with aiofiles.open(text_book_file, 'r', encoding='utf-8') as f:
        content = await f.read()

    # Split the source text into chunks.）
    tokens_per_chunk = max_tokens // 2
    chunks = []
    remaining_content = content

    while remaining_content:
        current_chunk = remaining_content
        current_tokens = count_tokens(current_chunk)

        if current_tokens <= tokens_per_chunk:
            chunks.append(current_chunk)
            break

        split_point = tokens_per_chunk
        sentence_end = max(
            remaining_content[:split_point].rfind(". "),
            remaining_content[:split_point].rfind("。"),
            remaining_content[:split_point].rfind("! "),
            remaining_content[:split_point].rfind("?"),
            remaining_content[:split_point].rfind("\n")
        )
        if sentence_end > 0 and sentence_end > len(remaining_content) // 4:
            split_point = sentence_end + 1

        chunks.append(remaining_content[:split_point])
        remaining_content = remaining_content[split_point:].lstrip()

    print(f"Split the file into {len(chunks)} chunks for asynchronous processing; maximum concurrency: {max_concurrent}")

    # Use a signal to control the number of simultaneous rounds
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(chunk, index):
        async with semaphore:
            return await process_chunk_async(chunk, index)

    # is recorded as
    tasks = [
        process_with_semaphore(chunk, i)
        for i, chunk in enumerate(chunks)
    ]

    # Run all chunk tasks.
    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.perf_counter()

    print(f"Asynchronous processing of all chunks completed; total elapsed time: {end_time - start_time:.2f} seconds")

    # Process result
    successful_results = []
    failed_count = 0

    for result in results:
        if isinstance(result, Exception):
            print(f"Task failed: {result}")
            failed_count += 1
        else:
            successful_results.append(result)

    if failed_count > 0:
        print(f"Warning: {failed_count} chunks failed")

    # Sort results by chunk index.
    successful_results.sort(key=lambda x: x["chunk_index"])

    # Merge Results
    refined_content_parts = [result["refined_content"] for result in successful_results]
    all_pck = []
    for result in successful_results:
        all_pck.extend(result["pck"])

    # Generate final content
    refined_content = "".join(refined_content_parts)
    all_sections = refined_content.split("xiaojiefenge")

    # Save the generated files.
    refined_file = f"{script_dir}/textbook_refined.txt"
    pck_file = f"{script_dir}/pck.json"
    sections_file = f"{script_dir}/sections.json"

    # Save all generated files.
    save_tasks = [
        save_text_file_async(refined_file, refined_content),
        save_json_file_async(pck_file, {"pck": all_pck}),
        save_json_file_async(sections_file, {"sections": all_sections})
    ]

    await asyncio.gather(*save_tasks)

    print(f"Refined content saved to: {refined_file}")
    print(f"Knowledge-point summary saved to: {pck_file}，{len(all_pck)} knowledge points")
    print(f"Sections saved to: {sections_file}，{len(all_sections)} sections")

    print(f"Asynchronous chunk processing complete: {len(all_sections)} sections.")
    return True

async def save_text_file_async(filepath: str, content: str):
    """Save a text file."""
    async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
        await f.write(content)

async def save_json_file_async(filepath: str, data: dict):
    """Step Save JSON Documentation"""
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
        await f.write(json_str)

if __name__ == "__main__":
    # Test Step Process
    textbook_file = "C:\\Users\\Aover\\Documents\\SchoolAgent_gitee\\agentschool\\teacher\\Textbook\\textbooks\\textbook.md"
    asyncio.run(textbook_pretreat(textbook_file))
