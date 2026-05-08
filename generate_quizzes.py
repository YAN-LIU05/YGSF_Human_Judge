import json
import random
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BENCHMARK_DIR = BASE_DIR.parent
IMAGE_ROOT = Path("/mnt/g/YGSF_new_color")
OUTPUT_DATA = BASE_DIR / "data" / "quizzes.json"
OUTPUT_IMAGES = BASE_DIR / "images"

QUIZ_COUNT = 10
QUESTIONS_PER_QUIZ = 100
CHOICE_COUNT = 8
SEED = 20260508

SOURCES = [
    {
        "key": "tie",
        "name": "帖",
        "meta_json": BENCHMARK_DIR / "tie_sample_90.json",
    },
    {
        "key": "bei",
        "name": "碑",
        "meta_json": BENCHMARK_DIR / "bei_sample_90.json",
    },
]

STYLE_DIR_MAP = {
    "行书": "行",
    "楷书": "楷",
    "草书": "草",
    "隶书": "隶",
    "篆书": "篆",
}

def rel_image(source_name, folder, filename):
    return f"{source_name}/{folder}/{filename}"


def copy_image(src, rel_path):
    dst = OUTPUT_IMAGES / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)


def remove_unused_images(used_rel_paths):
    if not OUTPUT_IMAGES.exists():
        return
    used = {Path(path) for path in used_rel_paths}
    for path in OUTPUT_IMAGES.rglob("*"):
        if path.is_file() and path.relative_to(OUTPUT_IMAGES) not in used:
            path.unlink(missing_ok=True)
    for path in sorted((p for p in OUTPUT_IMAGES.rglob("*") if p.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass


def main():
    if not IMAGE_ROOT.exists():
        raise FileNotFoundError(f"Missing processed image root: {IMAGE_ROOT}")

    rng = random.Random(SEED)
    quizzes = []
    copied = set()

    for source in SOURCES:
        meta_json = source["meta_json"]
        source_key = source["key"]
        source_name = source["name"]
        if not meta_json.exists():
            raise FileNotFoundError(f"Missing metadata: {meta_json}")

        metas = json.loads(meta_json.read_text(encoding="utf-8"))
        candidate_items = []
        for item in metas:
            if item.get("source_type") != source_name:
                continue
            style_dir = STYLE_DIR_MAP.get(item["script_type"])
            if not style_dir:
                continue
            label = f"{item['calligrapher']}-{style_dir}"
            candidate_items.append((item, label))

        label_to_desc = {}
        image_index = {}
        targets = []
        for item, label in candidate_items:
            filename = item["filename"]
            src = IMAGE_ROOT / label / filename
            label_to_desc.setdefault(label, item.get("description", ""))
            image_index.setdefault(label, []).append(src)
            targets.append(
                {
                    "filename": filename,
                    "char": item.get("char", ""),
                    "label": label,
                    "source_key": source_key,
                    "source_type": source_name,
                    "script_type": item["script_type"],
                    "calligrapher": item["calligrapher"],
                    "dynasty": item.get("dynasty", ""),
                    "description": item.get("description", ""),
                    "image": rel_image(source_name, label, filename),
                    "src": src,
                }
            )

        labels = sorted(label_to_desc)
        labels_with_images = [label for label in labels if image_index.get(label)]
        if len(labels_with_images) < CHOICE_COUNT:
            raise RuntimeError(f"Need at least {CHOICE_COUNT} {source_name} candidate labels with images.")
        if len(targets) < QUIZ_COUNT * QUESTIONS_PER_QUIZ:
            raise RuntimeError(f"Not enough {source_name} target images to build the requested quizzes.")

        rng.shuffle(targets)
        target_cursor = 0

        for quiz_index in range(QUIZ_COUNT):
            questions = []
            for question_index in range(QUESTIONS_PER_QUIZ):
                target = targets[target_cursor]
                target_cursor += 1
                correct_label = target["label"]

                correct_refs = [
                    p for p in image_index[correct_label]
                    if p.name != target["filename"]
                ]
                if not correct_refs:
                    raise RuntimeError(f"No reference image for {source_name}/{correct_label}/{target['filename']}")

                other_labels = [label for label in labels_with_images if label != correct_label]
                choice_labels = [correct_label] + rng.sample(other_labels, CHOICE_COUNT - 1)
                rng.shuffle(choice_labels)

                options = []
                for option_index, label in enumerate(choice_labels):
                    if label == correct_label:
                        ref_src = rng.choice(correct_refs)
                    else:
                        ref_src = rng.choice(image_index[label])
                    ref_rel = rel_image(source_name, label, ref_src.name)
                    options.append(
                        {
                            "id": chr(ord("A") + option_index),
                            "label": label,
                            "source_key": source_key,
                            "source_type": source_name,
                            "description": label_to_desc.get(label, ""),
                            "ref_image": ref_rel,
                        }
                    )
                    if ref_rel not in copied:
                        copy_image(ref_src, ref_rel)
                        copied.add(ref_rel)

                if target["image"] not in copied:
                    copy_image(target["src"], target["image"])
                    copied.add(target["image"])

                questions.append(
                    {
                        "id": f"{source_key.upper()}-Q{question_index + 1:03d}",
                        "target_image": target["image"],
                        "char": target["char"],
                        "source_key": source_key,
                        "source_type": source_name,
                        "answer": correct_label,
                        "answer_option": next(o["id"] for o in options if o["label"] == correct_label),
                        "meta": {
                            "filename": target["filename"],
                            "calligrapher": target["calligrapher"],
                            "script_type": target["script_type"],
                            "source_type": target["source_type"],
                            "dynasty": target["dynasty"],
                            "description": target["description"],
                        },
                        "options": options,
                    }
                )

            quizzes.append(
                {
                    "id": f"{source_key}-set-{quiz_index + 1:02d}",
                    "name": f"{source_name} 题库 {quiz_index + 1}",
                    "source_key": source_key,
                    "source_type": source_name,
                    "question_count": QUESTIONS_PER_QUIZ,
                    "choice_count": CHOICE_COUNT,
                    "questions": questions,
                }
            )

    OUTPUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DATA.write_text(
        json.dumps(
            {
                "generated_from": [str(source["meta_json"].name) for source in SOURCES],
                "image_root": "images",
                "seed": SEED,
                "quiz_count": len(quizzes),
                "quiz_count_per_source": QUIZ_COUNT,
                "questions_per_quiz": QUESTIONS_PER_QUIZ,
                "choice_count": CHOICE_COUNT,
                "quizzes": quizzes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    remove_unused_images(copied)
    print(f"Generated {len(quizzes)} quizzes x {QUESTIONS_PER_QUIZ} questions")
    print(f"Copied {len(copied)} images into {OUTPUT_IMAGES}")


if __name__ == "__main__":
    main()
