from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from ai_research_radar.schemas.models import ArticleProposal, HotCandidate


@dataclass(frozen=True)
class _RoleIdea:
    role: str
    article_type: str
    title: str
    technical_angle: str
    experiment_plan: list[str]
    priority: float
    risk: str


def generate_article_proposals(
    candidate: HotCandidate,
    max_proposals: int = 3,
) -> list[ArticleProposal]:
    if not candidate.evidence_urls:
        return []
    role_ideas = _deduplicate_role_ideas(_role_ideas(candidate))
    critiqued = [(_critique(candidate, idea), idea) for idea in role_ideas]
    critiqued.sort(key=lambda item: (-item[0][0], -item[1].priority, item[1].title))
    selected = critiqued[:max(0, max_proposals)]
    rejected = critiqued[max(0, max_proposals):]
    proposals: list[ArticleProposal] = []
    for index, ((critique_score, critique_notes), idea) in enumerate(selected, start=1):
        debate = _debate_summary(idea, critique_score, critique_notes, rejected)
        proposals.append(
            ArticleProposal(
                proposal_id=f"{candidate.hot_id}:proposal:{index}",
                source_hot_id=candidate.hot_id,
                title_idea=idea.title,
                article_type=idea.article_type,
                target_reader="AI Engineer",
                why_now=(
                    f"HOT score {candidate.score} with reasons: {', '.join(candidate.reasons)}. "
                    f"Role: {idea.role}. 軽量Critique score: {critique_score}/100; "
                    f"{' ; '.join(critique_notes)}. Debate: {debate}"
                ),
                technical_angle=idea.technical_angle,
                experiment_plan=idea.experiment_plan,
                competition="Unknown until content radar check",
                traffic_opportunity="High" if candidate.score >= 90 else "Medium",
                technical_opportunity="High",
                unique_angle=(
                    f"{idea.role}の観点で日本語の再現可能な検証を加える。"
                    f" Debate統合ではCriticの懸念を検証項目にする。"
                ),
                evidence_links=list(candidate.evidence_urls),
                risks=[
                    *[f"軽量Critique: {note}" for note in critique_notes],
                    f"Debate: {debate}",
                ],
            )
        )
    return proposals


def _role_ideas(candidate: HotCandidate) -> list[_RoleIdea]:
    explainer_title = f"{candidate.title}: 何が新しく、なぜ今注目されているのか"
    return [
        _RoleIdea("Explainer", "Technical Explainer", explainer_title,
                  "仕組み、背景、既存手法との差分を整理する。",
                  ["公式情報を確認", "主要機能を図解", "既存技術との差分を表にする"], 90,
                  "仕様の読み違いを避けるため、一次情報で用語を確認する。"),
        _RoleIdea("Hands-on Engineer", "Hands-on", f"{candidate.topic}を実際に動かして評価する",
                  "セットアップ、最小サンプル、つまずきどころを検証する。",
                  ["インストール", "サンプル実行", "失敗ケースと回避策を記録"], 86,
                  "実行環境による再現性の差を明記する。"),
        _RoleIdea("Comparison Analyst", "Comparison", f"{candidate.topic}を既存ツールと比較する",
                  "機能、拡張性、運用負荷、記事化価値を比較する。",
                  ["比較軸を定義", "既存ツールを選定", "表で評価"], 85,
                  "比較対象のバージョン差を固定する。"),
        _RoleIdea("Skeptic / Reviewer", "Critical Review", f"{candidate.topic}の導入前に検証したい限界",
                  "失敗条件、コスト、運用上の制約を検証する。",
                  ["失敗条件を列挙", "コストを測定", "代替案と比較"], 83,
                  "否定的な結論でも根拠と再現手順を残す。"),
        _RoleIdea("Benchmark Analyst", "Benchmark", f"{candidate.topic}をベンチマークで評価する",
                  "測定指標とワークロードを固定し、性能差を示す。",
                  ["ワークロードを固定", "指標を測定", "結果を再現"], 84,
                  "ベンチマークが実利用を代表しない可能性を注記する。"),
        _RoleIdea("Trend Analyst", "Trend Explainer", explainer_title,
                  "ニュース性と技術的な実態を分けて説明する。",
                  ["話題化の根拠を確認", "技術差分を確認", "読者需要を整理"], 76,
                  "話題性だけで有用性を断定しない。"),
    ]


def _deduplicate_role_ideas(ideas: list[_RoleIdea]) -> list[_RoleIdea]:
    kept: list[_RoleIdea] = []
    for idea in sorted(ideas, key=lambda item: (-item.priority, item.title, item.role)):
        if any(_title_similarity(idea.title, existing.title) >= 0.92 for existing in kept):
            continue
        kept.append(idea)
    return kept


def _title_similarity(first: str, second: str) -> float:
    return SequenceMatcher(None, "".join(first.lower().split()), "".join(second.lower().split())).ratio()


def _critique(candidate: HotCandidate, idea: _RoleIdea) -> tuple[float, list[str]]:
    notes = ["根拠URLは公開情報に限定されており、一次情報を本文で再確認する。"]
    if len(set(candidate.source_families)) < 2:
        notes.append("Source Familyが単一のため、他の独立Sourceでの裏付けを追加する。")
    if candidate.score < 90:
        notes.append("HOT scoreが急変し得るため、公開直前にMomentumを再確認する。")
    else:
        notes.append("高スコアでも累積人気と直近性を分けて検証する。")
    notes.append(idea.risk)
    score = min(100.0, max(0.0, candidate.score * 0.65 + idea.priority * 0.35))
    if len(set(candidate.source_families)) < 2:
        score -= 5.0
    return round(score, 2), notes


def _debate_summary(
    idea: _RoleIdea,
    critique_score: float,
    critique_notes: list[str],
    rejected: list[tuple[tuple[float, list[str]], _RoleIdea]],
) -> str:
    advocate = f"Advocateは{idea.role}が技術的な検証価値を示せると主張する"
    critic = f"Criticは{critique_notes[-1]}を確認するよう求める"
    editor = f"EditorはCritique score {critique_score}を根拠に採用する"
    if rejected:
        rejected_titles = ", ".join(item.title for _, item in rejected)
        editor += f"。却下候補: {rejected_titles} は優先度が低い"
    return f"{advocate}; {critic}; {editor}"
