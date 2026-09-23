from dataclasses import dataclass
from ..utils.text import contains_any, normalize_space

ANALYSIS_VERSION = 'rules-v2.0'

# Transparent first-pass signals. These are triage indicators, not legal conclusions.
SEVERE_INSULTS = [
    '쓰레기', '인간말종', '벌레', '개새끼', '씨발', '병신', '미친년', '미친놈',
    'trash human', 'piece of shit', 'scum',
]
INSULTS = [
    '멍청', '한심', '역겹', '혐오', '최악', '재수없', '싫어', '못생', '무능',
    'idiot', 'stupid', 'disgusting', 'awful',
]
THREATS = [
    '죽여', '죽이고', '죽였으면', '패버', '때려죽', '가만 안 둬', '가만두지',
    '찾아가서', '불태워', '칼로', '죽어라', 'kill you', 'beat you', 'hunt you down',
]
CRIME_ALLEGATIONS = [
    '사기쳤', '사기꾼', '횡령', '마약했', '성범죄', '성폭행', '강간', '도둑',
    '불법으로', '범죄자', '뇌물', '폭행했', '학폭했', 'embezzled', 'fraud', 'rapist',
]
PRIVACY_EXPOSURE = [
    '집주소', '주소는', '전화번호', '번호는 010', '사는 곳', '학교는', '회사 주소',
    'home address', 'phone number', 'lives at',
]
SEXUAL_SLURS = [
    '창녀', '걸레', '몸 팔', '성매매', 'whore', 'slut',
]
HEDGING = [
    '아마', '같다', '인 듯', '인것 같다', '라고 들었다', '소문', '확실하진',
    'maybe', 'apparently', 'rumor', 'i think',
]
OPINION_MARKERS = [
    '내 생각엔', '개인적으로', '취향이 아니다', '별로다', '연기가 별로', '노래가 별로',
    'i dislike', 'not my taste', 'in my opinion',
]


@dataclass
class AnalysisResult:
    risk_band: str
    risk_score: int
    reasons: list[str]
    signals: dict
    analysis_version: str = ANALYSIS_VERSION


def analyze_text(target: str, text: str, context: str = '', aliases: list[str] | None = None) -> AnalysisResult:
    text = normalize_space(text)
    context = normalize_space(context)
    combined = f'{text} {context}'.strip()
    target_names = [target] + [a for a in (aliases or []) if a]
    target_direct = any(name.casefold() in text.casefold() for name in target_names)
    target_in_context = any(name.casefold() in context.casefold() for name in target_names)

    signals = {
        'target_direct': target_direct,
        'target_in_context': target_in_context,
        'severe_insult': contains_any(text, SEVERE_INSULTS),
        'insult': contains_any(text, INSULTS),
        'threat': contains_any(text, THREATS),
        'crime_allegation': contains_any(text, CRIME_ALLEGATIONS),
        'privacy_exposure': contains_any(text, PRIVACY_EXPOSURE),
        'sexual_slur': contains_any(text, SEXUAL_SLURS),
        'hedging': contains_any(text, HEDGING),
        'opinion_marker': contains_any(text, OPINION_MARKERS),
    }

    score = 0
    reasons: list[str] = []

    if signals['target_direct']:
        score += 15
        reasons.append('본문에 대상이 직접 특정됩니다.')
    elif signals['target_in_context']:
        score += 8
        reasons.append('게시물 또는 영상 맥락에서 대상이 특정될 가능성이 있습니다.')

    if signals['threat']:
        score += 45
        reasons.append('위협 또는 위해 암시 표현이 감지되었습니다.')
    if signals['privacy_exposure']:
        score += 40
        reasons.append('주소·전화번호 등 개인정보 노출 신호가 감지되었습니다.')
    if signals['crime_allegation']:
        score += 35
        reasons.append('범죄·불법행위에 관한 사실 적시형 주장 신호가 감지되었습니다.')
    if signals['sexual_slur']:
        score += 25
        reasons.append('성적 비하 표현이 감지되었습니다.')
    if signals['severe_insult']:
        score += 25
        reasons.append('강한 모욕성 표현이 감지되었습니다.')
    elif signals['insult']:
        score += 14
        reasons.append('부정적·모욕적 표현이 감지되었습니다.')

    if signals['hedging']:
        score -= 8
        reasons.append('추측·전언 표현이 있어 맥락 확인이 필요합니다.')
    if signals['opinion_marker'] and not signals['crime_allegation'] and not signals['threat']:
        score -= 10
        reasons.append('의견·취향 표현 신호가 있어 법률적 의미가 낮을 수 있습니다.')

    # Without any relation to the target, strongly reduce priority.
    if not target_direct and not target_in_context:
        score -= 18
        reasons.append('대상 특정성이 약합니다.')

    score = max(0, min(100, score))
    if score >= 50:
        band = 'review_first'
    elif score >= 25:
        band = 'context_needed'
    else:
        band = 'low_priority'

    return AnalysisResult(
        risk_band=band,
        risk_score=score,
        reasons=reasons or ['뚜렷한 위험 신호가 적어 낮은 우선순위로 분류되었습니다.'],
        signals=signals,
    )
