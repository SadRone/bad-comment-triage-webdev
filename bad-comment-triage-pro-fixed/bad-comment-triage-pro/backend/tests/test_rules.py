from app.analysis.rules import analyze_text


def test_opinion_is_low():
    r = analyze_text('홍길동', '홍길동 연기는 개인적으로 별로다.')
    assert r.risk_band == 'low_priority'
    assert r.risk_score < 30


def test_crime_allegation_is_reviewable():
    r = analyze_text('홍길동', '홍길동은 사람들 돈을 사기쳤다.')
    assert r.risk_score >= 50
    assert r.signals['crime_allegation'] is True


def test_context_can_identify_target():
    r = analyze_text('홍길동', '진짜 쓰레기 같은 인간이다.', context='홍길동 인터뷰 영상')
    assert r.signals['target_in_context'] is True
    assert r.risk_score >= 30


def test_threat_is_high_priority():
    r = analyze_text('홍길동', '홍길동 찾아가서 가만 안 둔다.')
    assert r.risk_band == 'review_first'
