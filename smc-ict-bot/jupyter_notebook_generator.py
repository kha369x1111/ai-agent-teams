"""
═══════════════════════════════════════════════════════════════════
📓 Jupyter Notebook Generator
═══════════════════════════════════════════════════════════════════
أداة لتوليد Jupyter Notebooks من ملفات Python تلقائياً
═══════════════════════════════════════════════════════════════════
"""

import json
import os
from pathlib import Path


def py_to_ipynb(py_file: str, output_file: str, notebook_name: str = "Notebook"):
    """
    تحويل ملف Python إلى Jupyter Notebook

    يقسم الملف إلى cells بناءً على:
    - التعليقات الطويلة ("""docstring""")
    - Headers (===, ---)
    - كتل الكود
    """
    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()

    cells = []

    # Header
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [f"# 📓 {notebook_name}\n"]
    })

    # تقسيم المحتوى إلى cells
    lines = content.split('\n')
    current_cell = []
    current_type = "code"
    in_docstring = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Section header
        if line.startswith('# ╔') or line.startswith('# ═'):
            # حفظ الـ cell السابق
            if current_cell:
                if current_type == "markdown":
                    cells.append({
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": current_cell
                    })
                else:
                    cells.append({
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": current_cell
                    })

            current_cell = []
            current_type = "markdown"
            i += 1
            continue

        # Docstring
        if '"""' in line:
            if not in_docstring:
                # بداية docstring
                in_docstring = True
                if current_cell:
                    cells.append({
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": current_cell
                    })
                current_cell = []
                current_type = "markdown"
                line = line.replace('"""', '').strip()
                if line:
                    current_cell.append(line + '\n')
            else:
                # نهاية docstring
                in_docstring = False
                line = line.replace('"""', '').strip()
                if line:
                    current_cell.append(line + '\n')
                if current_cell:
                    cells.append({
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": current_cell
                    })
                current_cell = []
                current_type = "code"

            i += 1
            continue

        # تجميع
        if in_docstring:
            current_cell.append(line + '\n')
        else:
            current_cell.append(line + '\n')

        i += 1

    # آخر cell
    if current_cell:
        if current_type == "markdown":
            cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": current_cell
            })
        else:
            cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": current_cell
            })

    # إنشاء notebook
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.11"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    # حفظ
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    print(f"✅ Notebook created: {output_file}")
    print(f"📊 Cells: {len(cells)}")


if __name__ == "__main__":
    # تحويل Knowledge Base files إلى notebooks
    base_path = Path(__file__).parent

    notebooks = [
        ("notebooks/01_institutional_logic.py", "notebooks/01_Institutional_Trading_Logic.ipynb", "Institutional Trading Logic"),
        ("notebooks/02_price_action_mastery.py", "notebooks/02_Price_Action_Mastery.ipynb", "Price Action Mastery"),
    ]

    for py_file, ipynb_file, name in notebooks:
        py_path = base_path / py_file
        ipynb_path = base_path / ipynb_file

        if py_path.exists():
            py_to_ipynb(str(py_path), str(ipynb_path), name)
        else:
            print(f"⚠️ {py_file} not found")
