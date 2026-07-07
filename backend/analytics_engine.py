import os
import json
import sqlite3
import math
from typing import Dict, List, Tuple
from analytics_repository import db as analytics_db
from analyzer import SCORING_SETTINGS

def calculate_correlation(x: List[float], y: List[float]) -> float:
    """Computes the Pearson correlation coefficient between two variables."""
    n = len(x)
    if n < 2:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    den_y = sum((y[i] - mean_y) ** 2 for i in range(n))
    
    if den_x == 0.0 or den_y == 0.0:
        return 0.0
    return num / ((den_x * den_y) ** 0.5)

def get_performance_correlations() -> Dict[str, Dict[str, float]]:
    """Calculates correlation coefficients between all 8 scoring dimensions and views, retention, shares."""
    data = analytics_db.get_correlation_data()
    if len(data) < 2:
        return {}

    from analyzer import SCORING_SETTINGS
    factors = list(SCORING_SETTINGS["weights"].keys())
    metrics = ["views", "retention", "shares"]
    
    # Extract values
    factor_values = {f: [] for f in factors}
    metric_values = {m: [] for m in metrics}
    
    for row in data:
        try:
            scores = json.loads(row["detailed_scores"])
            for f in factors:
                factor_values[f].append(float(scores.get(f, 5.0)))
            metric_values["views"].append(float(row["views"]))
            metric_values["retention"].append(float(row["retention"]))
            metric_values["shares"].append(float(row["shares"]))
        except Exception:
            continue
            
    # Compute Pearson correlation matrix
    matrix = {}
    for f in factors:
        matrix[f] = {}
        for m in metrics:
            matrix[f][m] = calculate_correlation(factor_values[f], metric_values[m])
            
    return matrix

def generate_model_improvement_report() -> Tuple[dict, str]:
    """Generates weight updates and logs them to a markdown file in the artifacts directory."""
    matrix = get_performance_correlations()
    current_weights = SCORING_SETTINGS["weights"]
    
    if not matrix:
        fallback_report = {
            "status": "Insufficient Data",
            "message": "Need at least 2 clips with performance metrics to calculate correlations.",
            "recommended_weights": current_weights
        }
        return fallback_report, ""

    recommended_weights = {}
    adjustments = {}
    
    for factor, weight in current_weights.items():
        corr_views = matrix[factor]["views"]
        corr_ret = matrix[factor]["retention"]
        corr_shares = matrix[factor]["shares"]
        
        composite_corr = 0.4 * corr_views + 0.4 * corr_ret + 0.2 * corr_shares
        adjusted_w = weight * (1.0 + 0.5 * composite_corr)
        adjusted_w = max(0.02, adjusted_w)
        recommended_weights[factor] = adjusted_w
        adjustments[factor] = composite_corr
        
    total_w = sum(recommended_weights.values())
    for f in recommended_weights:
        recommended_weights[f] = round(recommended_weights[f] / total_w, 4)
        
    top_patterns = sorted(adjustments.items(), key=lambda x: x[1], reverse=True)[:3]
    worst_patterns = sorted(adjustments.items(), key=lambda x: x[1])[:3]
    
    report_data = {
        "status": "Success",
        "correlations": matrix,
        "current_weights": current_weights,
        "recommended_weights": recommended_weights,
        "top_performing_factors": [{"factor": f, "correlation": round(c, 4)} for f, c in top_patterns],
        "worst_performing_factors": [{"factor": f, "correlation": round(c, 4)} for f, c in worst_patterns]
    }
    
    report_path = "C:/Users/anils/.gemini/antigravity/brain/1b3acd38-6039-400c-975c-a12268af0711/model_improvement_report.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Model Improvement Report (Phase 9)\n\n")
        f.write("This report details evidence-based updates to ClipMind's scoring engine derived from platform performance metrics.\n\n")
        
        f.write("## 📊 Correlation Matrix (Pearson $r$)\n\n")
        f.write("| Scoring Factor | Correlation with Views | Correlation with Retention | Correlation with Shares | Composite Score |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: |\n")
        for factor in matrix:
            comp = 0.4 * matrix[factor]["views"] + 0.4 * matrix[factor]["retention"] + 0.2 * matrix[factor]["shares"]
            f.write(f"| **{factor}** | {matrix[factor]['views']:.4f} | {matrix[factor]['retention']:.4f} | {matrix[factor]['shares']:.4f} | **{comp:.4f}** |\n")
            
        f.write("\n## ⚙️ Weights Recommender System\n\n")
        f.write("| Factor | Current Weight | Recommended Weight | Change |\n")
        f.write("| :--- | :---: | :---: | :---: |\n")
        for factor in current_weights:
            diff = recommended_weights[factor] - current_weights[factor]
            diff_str = f"+{diff:.4f}" if diff >= 0 else f"{diff:.4f}"
            f.write(f"| **{factor}** | {current_weights[factor]:.4f} | {recommended_weights[factor]:.4f} | **{diff_str}** |\n")
            
        f.write("\n## 🔍 Highlights\n\n")
        f.write(f"1. **Strongest Predictor**: `{top_patterns[0][0]}` shows the highest correlation with video performance ($r = {top_patterns[0][1]:.4f}$).\n")
        f.write(f"2. **Weakest Predictor**: `{worst_patterns[0][0]}` shows the lowest correlation with performance ($r = {worst_patterns[0][1]:.4f}$).\n\n")
        
        f.write("## 🗺️ Future Optimization Roadmap\n\n")
        f.write("* **Machine Learning Regression**: Train a linear regression or Random Forest model once data hits 500+ records to refine weights.\n")
        f.write("* **Ranking Model Optimization**: Implement a pairwise ranking model (e.g. LambdaMART) to directly optimize clip recommendations.\n")
        
    return report_data, report_path

def calculate_welch_t_test(x1: List[float], x2: List[float]) -> Tuple[float, float, float]:
    """
    Computes Welch's t-test for unequal variances and sizes.
    Returns: (t_statistic, p_value, confidence_level)
    """
    n1 = len(x1)
    n2 = len(x2)
    if n1 < 2 or n2 < 2:
        return 0.0, 1.0, 0.0
        
    mean1 = sum(x1) / n1
    mean2 = sum(x2) / n2
    
    var1 = sum((x - mean1) ** 2 for x in x1) / (n1 - 1)
    var2 = sum((x - mean2) ** 2 for x in x2) / (n2 - 1)
    
    denom = (var1 / n1 + var2 / n2) ** 0.5
    if denom == 0:
        return 0.0, 1.0, 0.0
        
    t_stat = (mean1 - mean2) / denom
    
    # Degrees of freedom (Welch-Satterthwaite)
    num_df = (var1 / n1 + var2 / n2) ** 2
    den_df = ((var1 / n1) ** 2) / (n1 - 1) + ((var2 / n2) ** 2) / (n2 - 1)
    df = num_df / den_df if den_df != 0 else (n1 + n2 - 2)
    
    # Normal approximation for t-distribution CDF
    abs_t = abs(t_stat)
    if df > 1:
        z = abs_t * (1.0 - 1.0 / (4.0 * df)) / ((1.0 + (t_stat ** 2) / (2.0 * df)) ** 0.5)
    else:
        z = abs_t
        
    # Standard normal two-tailed p-value
    p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / (2.0 ** 0.5))))
    confidence = (1.0 - p_val) * 100.0
    
    return round(t_stat, 4), round(p_val, 4), round(confidence, 2)

def analyze_ab_test() -> dict:
    """
    Performs normalized performance calculations and Welch's t-test for exp_virality_v1.
    Normalizes views, retention, and shares using min-max scaling across all records.
    """
    records = analytics_db.get_all_records()
    if not records:
        return {
            "status": "Experiment Running - More Data Required",
            "sample_size_A": 0,
            "sample_size_B": 0,
            "confidence_level": 0.0,
            "p_value": 1.0,
            "t_statistic": 0.0,
            "current_leader": None,
            "winner": None,
            "message": "No data available in analytics database."
        }
        
    # Extract performance metrics
    views_list = [float(r["views"]) for r in records]
    ret_list = [float(r["retention"]) for r in records]
    shares_list = [float(r["shares"]) for r in records]
    
    max_v, min_v = max(views_list), min(views_list)
    max_r, min_r = max(ret_list), min(ret_list)
    max_s, min_s = max(shares_list), min(shares_list)
    
    # Calculate composite score for each record
    scores_A = []
    scores_B = []
    
    for r in records:
        # Check if record belongs to active experiment 'exp_virality_v1'
        exp_id = r.get("experiment_id") or "exp_virality_v1"
        if exp_id != "exp_virality_v1":
            continue
            
        variant = r.get("variant_id") or r.get("scoring_version") or "A"
        
        # Min-Max Normalization to [0.0, 10.0]
        norm_v = 10.0 * (float(r["views"]) - min_v) / (max_v - min_v) if max_v > min_v else 5.0
        norm_r = 10.0 * (float(r["retention"]) - min_r) / (max_r - min_r) if max_r > min_r else 5.0
        norm_s = 10.0 * (float(r["shares"]) - min_s) / (max_s - min_s) if max_s > min_s else 5.0
        
        composite = 0.4 * norm_v + 0.4 * norm_r + 0.2 * norm_s
        
        if variant == "A":
            scores_A.append(composite)
        elif variant == "B":
            scores_B.append(composite)
            
    n_A = len(scores_A)
    n_B = len(scores_B)
    
    if n_A < 2 or n_B < 2:
        return {
            "status": "Experiment Running - More Data Required",
            "sample_size_A": n_A,
            "sample_size_B": n_B,
            "confidence_level": 0.0,
            "p_value": 1.0,
            "t_statistic": 0.0,
            "current_leader": None,
            "winner": None,
            "message": "Not enough variant observations. Need at least 2 in each variant."
        }
        
    mean_A = sum(scores_A) / n_A
    mean_B = sum(scores_B) / n_B
    
    t_stat, p_val, conf = calculate_welch_t_test(scores_A, scores_B)
    
    # Leader selection based on mean composite score
    leader = "A" if mean_A > mean_B else "B"
    if mean_A == mean_B:
        leader = "Tie"
        
    # Apply statistical and sample size guardrails
    MIN_SAMPLE_SIZE = 30
    MIN_CONFIDENCE = 95.0
    
    thresholds_met = (n_A >= MIN_SAMPLE_SIZE and n_B >= MIN_SAMPLE_SIZE and conf >= MIN_CONFIDENCE)
    
    if thresholds_met:
        winner = leader if leader != "Tie" else None
        status = "Statistically Significant Winner Declared"
    else:
        winner = None
        status = "Experiment Running - More Data Required"
        
    return {
        "status": status,
        "sample_size_A": n_A,
        "sample_size_B": n_B,
        "mean_composite_A": round(mean_A, 4),
        "mean_composite_B": round(mean_B, 4),
        "t_statistic": t_stat,
        "p_value": p_val,
        "confidence_level": conf,
        "current_leader": leader,
        "winner": winner,
        "thresholds_met": thresholds_met
    }

def generate_experiment_report() -> Tuple[dict, str]:
    """Generates the A/B testing Experiment Report and writes it as a markdown artifact and JSON file."""
    report_data = analyze_ab_test()
    
    report_path = "C:/Users/anils/.gemini/antigravity/brain/1b3acd38-6039-400c-975c-a12268af0711/experiment_report.md"
    dashboard_path = "C:/Users/anils/.gemini/antigravity/brain/1b3acd38-6039-400c-975c-a12268af0711/experiment_dashboard.json"
    
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    # Save dashboard state JSON
    with open(dashboard_path, "w", encoding="utf-8") as json_f:
        json.dump(report_data, json_f, indent=2)
        
    # Write Markdown Report
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# A/B Test Experimentation Report (Phase 10)\n\n")
        f.write("This report details statistical performance attribution comparing Variant A (Baseline) and Variant B (High Hook strength).\n\n")
        
        status_color = "🟢" if report_data["thresholds_met"] else "🟡"
        f.write(f"## {status_color} Experiment Status: **{report_data['status']}**\n\n")
        
        f.write("### 📊 Metrics Comparison\n\n")
        f.write("| Variant | Sample Size (N) | Mean Composite Score | Weight Config |\n")
        f.write("| :--- | :---: | :---: | :--- |\n")
        f.write(f"| **Variant A (Baseline)** | {report_data['sample_size_A']} | {report_data.get('mean_composite_A', 0.0):.4f} | hook_strength=20%, first_3_sec=25% |\n")
        f.write(f"| **Variant B (High Hook)** | {report_data['sample_size_B']} | {report_data.get('mean_composite_B', 0.0):.4f} | hook_strength=30%, first_3_sec=25% |\n\n")
        
        f.write("### 🔬 Statistical Engine (Welch's t-test)\n\n")
        f.write(f"- **t-statistic**: `{report_data['t_statistic']}`\n")
        f.write(f"- **p-value**: `{report_data['p_value']}`\n")
        f.write(f"- **Confidence Level**: `{report_data['confidence_level']}%` *(Target: $\\ge 95\\%$)*\n")
        f.write(f"- **Current Leader**: Variant `{report_data['current_leader']}`\n")
        f.write(f"- **Declared Winner**: `{report_data['winner'] or 'None (Gathering Data)'}`\n\n")
        
        f.write("### 🛡️ Guardrails Audit\n\n")
        f.write("| Guardrail | Requirement | Current Value | Status |\n")
        f.write("| :--- | :---: | :---: | :---: |\n")
        f.write(f"| Minimum Sample Size (A) | $\\ge 30$ | {report_data['sample_size_A']} | {'✅ Pass' if report_data['sample_size_A'] >= 30 else '❌ Fail'} |\n")
        f.write(f"| Minimum Sample Size (B) | $\\ge 30$ | {report_data['sample_size_B']} | {'✅ Pass' if report_data['sample_size_B'] >= 30 else '❌ Fail'} |\n")
        f.write(f"| Minimum Confidence | $\\ge 95.0\\%$ | {report_data['confidence_level']}% | {'✅ Pass' if report_data['confidence_level'] >= 95.0 else '❌ Fail'} |\n\n")
        
        if report_data["winner"]:
            f.write(f"> [!IMPORTANT]\n")
            f.write(f"> **Variant {report_data['winner']} is the statistically validated winner!** Its scoring configuration will now be recommended for default production weights.\n")
        else:
            f.write(f"> [!NOTE]\n")
            f.write(f"> Experiment is still running. Both variants must accumulate 30+ observations with $\\ge 95\\%$ confidence before a winner is declared.\n")
            
    return report_data, report_path

def generate_creator_disagreement_report() -> Tuple[dict, str]:
    """Generates the expanded Creator Disagreement Report comparing ClipMind heuristic scores with actual creator choices and providing probable causes."""
    records = analytics_db.get_all_records()
    
    false_positives = []
    false_negatives = []
    
    for r in records:
        clip_id = r["clip_id"]
        v_score = r["virality_score"]
        selected = bool(r["creator_selected"])
        rejected = bool(r["creator_rejected"])
        
        try:
            det = json.loads(r["detailed_scores"])
        except Exception:
            det = {}
            
        clip_info = {
            "clip_id": clip_id,
            "video_id": r["video_id"],
            "virality_score": v_score,
            "detailed_scores": det,
            "feedback": r["feedback"],
            "creator_action": "Rejected" if rejected else ("Selected" if selected else "Pending")
        }
        
        # Heuristic probable cause analyzer
        if v_score >= 7.5 and rejected:
            # Overvalued: High score, creator rejected
            contr = det.get("controversy", 5.0)
            story = det.get("storytelling", 5.0)
            act = det.get("actionability", 5.0)
            
            if contr >= 8.0:
                cause = "High controversy rating. Creators often reject controversial clips to protect brand safety and sponsor alignment."
            elif story >= 8.0 and act <= 5.0:
                cause = "High storytelling score but low practical utility. Creator preferred highly educational/actionable content instead of generic narrative."
            else:
                cause = "Heuristic overvalued the opening second hooks, but the actual clip content lacked educational substance or brand alignment."
                
            clip_info["probable_cause"] = cause
            false_positives.append(clip_info)
            
        elif v_score <= 5.0 and selected:
            # Undervalued: Low score, creator selected
            act = det.get("actionability", 5.0)
            story = det.get("storytelling", 5.0)
            hook = det.get("first_3_second_hook", 5.0)
            
            if act >= 7.0 and hook <= 5.0:
                cause = "High educational value. Creator selected this clip for its practical utility despite a slow-building opening hook."
            elif story >= 7.0 and hook <= 5.0:
                cause = "Slow-building personal narrative. Creator valued the deep storytelling arc despite failing the initial hook speed heuristics."
            else:
                cause = "Creator identified high niche relevance or audience-specific value that standard virality heuristics failed to register."
                
            clip_info["probable_cause"] = cause
            false_negatives.append(clip_info)
            
    report_data = {
        "status": "Success",
        "false_positives_count": len(false_positives),
        "false_negatives_count": len(false_negatives),
        "false_positives": false_positives,
        "false_negatives": false_negatives
    }
    
    report_path = "C:/Users/anils/.gemini/antigravity/brain/1b3acd38-6039-400c-975c-a12268af0711/creator_disagreement_report.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Creator Disagreement Report (Phase 10)\n\n")
        f.write("This report analyzes discrepancies between ClipMind's automated scoring heuristics and actual creator selection behaviors.\n\n")
        
        f.write("## 📈 Summary Statistics\n\n")
        f.write(f"- **Heuristically Overvalued (False Positives)**: {len(false_positives)} clips rejected by creators despite a high score ($\\ge 7.5$).\n")
        f.write(f"- **Heuristically Undervalued (False Negatives)**: {len(false_negatives)} clips selected by creators despite a low score ($\\le 5.0$).\n\n")
        
        f.write("## ❌ Overvalued Clips (ClipMind $\\ge 7.5$, Creator Rejected)\n\n")
        if not false_positives:
            f.write("No false positives recorded.\n")
        else:
            f.write("| Clip ID | Video ID | Virality Score | High Scores Breakdown | Creator Action | Probable Cause |\n")
            f.write("| :--- | :--- | :---: | :--- | :---: | :--- |\n")
            for c in false_positives:
                det = c["detailed_scores"]
                high_factors = [f"{k}={v}" for k, v in det.items() if isinstance(v, (int, float)) and v >= 8.0]
                f.write(f"| `{c['clip_id']}` | `{c['video_id']}` | {c['virality_score']:.2f} | {', '.join(high_factors)} | **{c['creator_action']}** | {c['probable_cause']} |\n")
                
        f.write("\n## 🔍 Undervalued Clips (ClipMind $\\le 5.0$, Creator Selected)\n\n")
        if not false_negatives:
            f.write("No false negatives recorded.\n")
        else:
            f.write("| Clip ID | Video ID | Virality Score | Low Scores Breakdown | Creator Action | Probable Cause |\n")
            f.write("| :--- | :--- | :---: | :--- | :---: | :--- |\n")
            for c in false_negatives:
                det = c["detailed_scores"]
                low_factors = [f"{k}={v}" for k, v in det.items() if isinstance(v, (int, float)) and v <= 4.0]
                f.write(f"| `{c['clip_id']}` | `{c['video_id']}` | {c['virality_score']:.2f} | {', '.join(low_factors)} | **{c['creator_action']}** | {c['probable_cause']} |\n")
                
    return report_data, report_path

def seed_experiment_data():
    """Seeds the database with 80+ records for Variant A and Variant B testing."""
    import random
    
    # Clear existing database records
    conn = sqlite3.connect(analytics_db.db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clip_analytics")
    conn.commit()
    conn.close()
    
    from analyzer import ACTIVE_EXPERIMENT
    factors = list(ACTIVE_EXPERIMENT["variants"]["A"]["weights"].keys())
    platforms = ["YouTube Shorts", "TikTok", "Instagram Reels"]
    
    random.seed(42)
    
    for i in range(1, 81):
        clip_id = f"c_{2000 + i}"
        video_id = f"v_{100 + (i // 4)}"
        
        variant_id = "A" if (i % 2 == 1) else "B"
        scoring_version = variant_id
        prompt_version = "prompt_v1"
        weight_version = "weight_v1_baseline" if variant_id == "A" else "weight_v2_high_hook"
        
        scores = {}
        for f in factors:
            scores[f] = random.randint(4, 10)
            
        if variant_id == "A":
            scores["hook_strength"] = random.randint(4, 7)
            scores["first_3_second_hook"] = random.randint(4, 7)
            views = random.randint(1000, 6000)
            retention = random.uniform(30.0, 55.0)
            shares = random.randint(10, 150)
        else:
            scores["hook_strength"] = random.randint(8, 10)
            scores["first_3_second_hook"] = random.randint(8, 10)
            views = random.randint(8000, 24000)
            retention = random.uniform(65.0, 92.0)
            shares = random.randint(200, 1200)
            
        likes = int(views * random.uniform(0.05, 0.10))
        comments = int(views * random.uniform(0.005, 0.015))
        watch_time = round(views * (retention / 100.0) * 0.5, 2)
        
        variant_weights = ACTIVE_EXPERIMENT["variants"][variant_id]["weights"]
        virality_score = sum(scores.get(f, 5.0) * w for f, w in variant_weights.items())
            
        analytics_db.save_clip_metadata(
            video_id=video_id,
            clip_id=clip_id,
            virality_score=round(virality_score, 2),
            detailed_scores=scores,
            experiment_id="exp_virality_v1",
            variant_id=variant_id,
            scoring_version=scoring_version,
            prompt_version=prompt_version,
            weight_version=weight_version
        )
        
        analytics_db.update_clip_analytics(
            clip_id=clip_id,
            platform=random.choice(platforms),
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            watch_time=watch_time,
            retention=retention,
            upload_date=f"2026-06-{random.randint(1, 18):02d}"
        )
        
        selected = False
        rejected = False
        published = False
        
        if scores["storytelling"] >= 7 or scores["actionability"] >= 7:
            selected = True
            published = random.choice([True, False])
        else:
            rejected = True
            
        # Disagreements
        if i == 10:
            scores["controversy"] = 9
            scores["hook_strength"] = 9
            scores["first_3_second_hook"] = 8
            virality_score = 7.9
            analytics_db.save_clip_metadata(
                video_id=video_id, clip_id=clip_id, virality_score=virality_score, detailed_scores=scores,
                experiment_id="exp_virality_v1", variant_id=variant_id,
                scoring_version=scoring_version, prompt_version=prompt_version, weight_version=weight_version
            )
            selected = False
            rejected = True
            published = False
            analytics_db.submit_clip_feedback(clip_id, "Too controversial for sponsor guidelines.")
        elif i == 11:
            scores["storytelling"] = 9
            scores["actionability"] = 3
            virality_score = 8.1
            analytics_db.save_clip_metadata(
                video_id=video_id, clip_id=clip_id, virality_score=virality_score, detailed_scores=scores,
                experiment_id="exp_virality_v1", variant_id=variant_id,
                scoring_version=scoring_version, prompt_version=prompt_version, weight_version=weight_version
            )
            selected = False
            rejected = True
            published = False
            analytics_db.submit_clip_feedback(clip_id, "Nice story but lacks practical value for our tutorials.")
        elif i == 20:
            scores["actionability"] = 8
            scores["first_3_second_hook"] = 3
            scores["hook_strength"] = 3
            virality_score = 4.2
            analytics_db.save_clip_metadata(
                video_id=video_id, clip_id=clip_id, virality_score=virality_score, detailed_scores=scores,
                experiment_id="exp_virality_v1", variant_id=variant_id,
                scoring_version=scoring_version, prompt_version=prompt_version, weight_version=weight_version
            )
            selected = True
            rejected = False
            published = True
        elif i == 21:
            scores["storytelling"] = 8
            scores["first_3_second_hook"] = 3
            scores["hook_strength"] = 4
            virality_score = 4.6
            analytics_db.save_clip_metadata(
                video_id=video_id, clip_id=clip_id, virality_score=virality_score, detailed_scores=scores,
                experiment_id="exp_virality_v1", variant_id=variant_id,
                scoring_version=scoring_version, prompt_version=prompt_version, weight_version=weight_version
            )
            selected = True
            rejected = False
            published = True
            
        analytics_db.update_creator_action(clip_id, selected=selected, rejected=rejected, published=published)
        
    return {"status": "success", "message": "Successfully seeded 80 A/B testing records."}

def compile_analytics_export(export_path: str = "output/analytics_export.csv") -> str:
    """
    Compiles all clip records into a single CSV including virality scores, scoring factors,
    creator actions/feedback, and platform performance metrics.
    """
    import csv
    records = analytics_db.get_all_records()
    
    export_dir = os.path.dirname(export_path)
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        
    headers = [
        "clip_id", "virality_score", "hook_strength", "first_3_second_hook",
        "curiosity_gap", "emotional_intensity", "controversy", "surprise",
        "actionability", "storytelling", "feedback", "creator_selected",
        "creator_rejected", "views", "likes", "comments", "watch_time", "retention"
    ]
    
    with open(export_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for r in records:
            try:
                scores = json.loads(r["detailed_scores"])
            except Exception:
                scores = {}
                
            row = [
                r["clip_id"],
                r["virality_score"],
                scores.get("hook_strength", ""),
                scores.get("first_3_second_hook", ""),
                scores.get("curiosity_gap", ""),
                scores.get("emotional_intensity", ""),
                scores.get("controversy", ""),
                scores.get("surprise", ""),
                scores.get("actionability", ""),
                scores.get("storytelling", ""),
                r.get("feedback") or "",
                r.get("creator_selected") or 0,
                r.get("creator_rejected") or 0,
                r.get("views") or 0,
                r.get("likes") or 0,
                r.get("comments") or 0,
                r.get("watch_time") or 0.0,
                r.get("retention") or 0.0
            ]
            writer.writerow(row)
            
    return export_path

