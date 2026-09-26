"""Author disclosed local acceptance fixtures. These are not an official holdout."""
import hashlib
import json
from pathlib import Path


def build():
    cases = []
    def add(kind, steps, **extra):
        cases.append(dict(id=f"{kind}-{sum(c['category']==kind for c in cases)+1:02d}", category=kind, steps=steps, **extra))
    def step(query, gold, **extra):
        return dict(text=query, gold=gold, **extra)
    singles = [
        ("How long is the LumaPad S1 limited warranty?", "LumaPad_S1 §Warranty.1"),
        ("What proof opens a LumaPad S1 repair?", "LumaPad_S1 §Repair.1"),
        ("What is the LumaPad S2 battery coverage period?", "LumaPad_S2 §Battery.1"),
        ("What video history does LumaCam C1 Basic retain?", "LumaCam_C1 §Cloud.1"),
        ("How long is the LumaCam C1 free Plus trial?", "LumaCam_C1 §Cloud.2"),
        ("Where is LumaCam C2 activity-zone analysis processed?", "LumaCam_C2 §Privacy.1"),
        ("When should the LumaAir A1 PureAir filter be replaced?", "LumaAir_A1 §Maintenance.1"),
        ("How do I reset the LumaAir A1 filter reminder?", "LumaAir_A1 §Setup.1"),
        ("What app version is required for LumaHub H1 setup?", "LumaHub_H1 §Setup.1"),
        ("When can I cancel CarePlus for a full refund?", "CarePlus §Cancellation.1")]
    for q,g in singles:
        add("single", [step(q,[g])])
    compound = [
        ("LumaPad S1", "what is the warranty period", "what proof opens a repair", "Warranty.1", "Repair.1"),
        ("LumaPad S1", "what liquid damage is excluded", "what receipt is required for repair", "Warranty.2", "Repair.1"),
        ("LumaPad S1", "what is the warranty period", "what liquid damage is excluded", "Warranty.1", "Warranty.2"),
        ("LumaPad S2", "what is the warranty period", "what battery capacity coverage applies", "Warranty.1", "Battery.1"),
        ("LumaPad S2", "what is the battery coverage", "where must warranty repairs be completed", "Battery.1", "Repair.1"),
        ("LumaCam C1", "what is the warranty period", "how much Basic video history is kept", "Warranty.1", "Cloud.1"),
        ("LumaCam C1", "how long is the free Plus trial", "how much Basic history is retained", "Cloud.2", "Cloud.1"),
        ("LumaCam C2", "what is the warranty period", "where is activity-zone analysis processed", "Warranty.1", "Privacy.1"),
        ("LumaCam C2", "how much Basic video history is kept", "where is activity-zone analysis processed", "Cloud.1", "Privacy.1"),
        ("LumaAir A1", "what is the warranty period", "when do I replace the PureAir filter", "Warranty.1", "Maintenance.1"),
        ("LumaAir A1", "when do I replace the PureAir filter", "how do I reset the filter reminder", "Maintenance.1", "Setup.1"),
        ("LumaAir A2", "when do I replace the PureAir filter", "which Wi-Fi network is needed for setup", "Maintenance.1", "Setup.1"),
        ("LumaWash W1", "what is motor warranty coverage", "when should the inlet hose be replaced", "Warranty.1", "Maintenance.1"),
        ("LumaHub H1", "what is the warranty period", "which app version is needed for setup", "Warranty.1", "Setup.1"),
        ("CarePlus", "when may I purchase the plan", "when can I get a cancellation refund", "Purchase.1", "Cancellation.1")]
    for entity,a,b,ga,gb in compound:
        doc=entity.replace(" ","_")
        add("compound", [step(f"For {entity}, {a} and {b}?", [f"{doc} §{ga}",f"{doc} §{gb}"])], intent_count=2)
    changes=[("LumaPad S1","LumaPad S2"),("LumaCam C1","LumaCam C2"),("LumaAir A1","LumaAir A2"),("LumaPad S2","LumaPad S1"),("LumaCam C2","LumaCam C1")]
    for old,new in changes:
        for form in ["What is the limited warranty for {}?", "How long is the warranty on {}?"]:
            query=form.format(new)
            add("correction", [step(query,[new.replace(" ","_")+" §Warranty.1"], prefixes=[form.format(old).rstrip('?'),form.format(old).rstrip('?')+' period'], correct=True)])
    for old,new in changes:
        add("refinement", [step(f"{old} warranty period",[old.replace(' ','_')+' §Warranty.1']),step(f"Actually {new} instead",[new.replace(' ','_')+' §Warranty.1'], delta=True)])
    for phrasing in ["What about warranty liquid damage exclusions?", "Actually warranty exclusions for liquid damage", "How about warranty liquid damage?", "For warranty, what about liquid damage?", "What about the liquid damage warranty exclusions?"]:
        add("refinement", [step("For LumaPad S1, what is the warranty period and what receipt opens a repair?",["LumaPad_S1 §Warranty.1","LumaPad_S1 §Repair.1"]),step(phrasing,["LumaPad_S1 §Warranty.2","LumaPad_S1 §Repair.1"],delta=True,preserve=1)])
    for phrase in ["Put that in bullets", "Show that as bullets", "Repeat the answer"]:
        add("presentation", [step("LumaPad S1 warranty period",["LumaPad_S1 §Warranty.1"]),step(phrase,["LumaPad_S1 §Warranty.1"],suppress=True)])
    for phrase in ["Put that in bullets and what is the LumaPad S2 battery coverage?", "Show that in bullets and what is the LumaAir A1 filter replacement period?"]:
        gold="LumaPad_S2 §Battery.1" if "S2" in phrase else "LumaAir_A1 §Maintenance.1"
        add("presentation", [step("LumaPad S1 warranty period",["LumaPad_S1 §Warranty.1"]),step(phrase,[gold],mixed=True)])
    for query in ["What telepathy features does LumaPad S1 offer?", "Does LumaCam C1 support teleportation?", "What is the retail price of LumaAir A1?", "Who is the CEO of LumaHome?", "What is the lunar warranty exception?", "What colors does LumaPad S2 come in?", "Does CarePlus cover cryptocurrency losses?", "What is the LumaPad X99 warranty period?", "What is LumaFridge F1 solar charging voltage?", "What are LumaWash W1 nuclear reactor specifications?"]:
        add("unsupported", [step(query,[],uncertain=True)])
    assert len(cases)==60
    root=Path(__file__).parent
    path=root/'acceptance-v1.json'
    path.write_text(json.dumps({"disclosure":"Locally authored acceptance suite. Known to the implementation author; not an independent blind holdout or Samsung evaluation.","cases":cases},ensure_ascii=False,indent=2),encoding='utf-8')
    dev=[]
    for n in range(120):
        q,g=singles[n%len(singles)]
        dev.append(dict(id=f"dev-{n+1:03d}",family=f"single-{n%10}",text=[q,'Please '+q[0].lower()+q[1:],'Tell me: '+q][n//10%3],gold=[g],stream_prefix_words=1+n%6))
    (root/'development-v1.json').write_text(json.dumps({"disclosure":"120 development replay variants from 10 query families; correlated variants, not 120 independent queries.","cases":dev},ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'dataset-manifest.json').write_text(json.dumps({"acceptance_cases":60,"acceptance_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"development_variants":120,"development_families":10,"official_validation":"pending"},indent=2),encoding='utf-8')


if __name__ == '__main__':
    build()
