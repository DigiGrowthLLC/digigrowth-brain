"""fal.ai was out of credit (2026-11-26): build the two AI UGCs from approved footage only.
ugc-thursday   = generic first line + Jennifer's review card + offer end card (no city line, no $175 line)
ugc-square-one = generic first line + cached "first visit's 49 bucks, only 10 spots" take + Mark's review + end card
Once fal has credit, delete this and run default_ai_ads.py --generate for the full versions."""
import pathlib, sys
REPO = pathlib.Path(r"C:/Users/dylan/Videos/Business/AI Agents/DigiGrowth-Brain")
sys.path.insert(0, str(REPO / "design-agent/tools"))
import default_ai_ads as da
da.ACTORS["ugc-thursday"]["takes"] = []
sq = da.ACTORS["ugc-square-one"]
sq["takes"] = [t for t in sq["takes"] if t[0] == "sq-t3"]
b = da.Builder(pathlib.Path(__file__).resolve().parent.parent / "blueprint.json", False)
for n in da.ACTORS:
    b.ugc(n)
