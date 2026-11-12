import pandas as pd
import re
from pathlib import Path

SNAPSHOTS_DIR = Path("data/snapshots")
WEEKS = ["2026-W44", "2026-W45", "2026-W46"]

# ============================================================
# ДАННЫЕ (по ID ссылки)
# ============================================================
DATA = {
    "1C": {
        "2ba80a6a-1a47-4b2e-b5bb-7ce15fd00ca7": (0, 0),
        "5b35eeb5-6eb9-4f2e-88f5-3b967e998e42": (0, 37627651),
        "612d8d07-433c-4268-b198-18b637050f48": (0, 11567270),
        "e3f183d8-86bc-482d-b183-85c886514e06": (0, 0),
        "baa06374-9824-4480-877b-197ad575c7cd": (0, 0),
        "b4f72574-28ce-4803-b4c5-6476fd7c3e84": (0, 0),
        "01073c55-39cc-444d-af2c-589b7e9fd1be": (0, 0),
        "9a66d047-c85b-437d-9fd7-83f3bdd34a1c": (0, 0),
        "8be615c7-48dd-4ec9-9ed4-bd03801f1c9d": (0, 0),
        "d06403f7-dbbb-4926-9b41-201f419fb59c": (0, 0),
        "c3aa21c2-ef3c-4696-917b-7a25d93ac2a4": (0, 0),
        "d0b6e0d4-b3af-43c8-9baa-1aa1ac09c76e": (0, 0),
        "3fb79b53-029d-46d5-81dc-e5bd4fc749df": (0, 0),
        "34d939c0-f2c9-4d06-a9e9-135cbea579e9": (0, 0),
        "4a68efee-8479-45c9-8261-7ced393b386e": (0, 0),
        "554a8da5-3238-4a45-9533-76c16d464747": (0, 0),
        "fd97e19f-ac42-43b3-a0cf-b3087fb25c42": (0, 0),
        "f9a483b4-17a2-40f5-9c34-dfb4bf0f22ca": (0, 0),
        "c008f1ef-e2cd-4490-bbca-e354d483c733": (0, 0),
        "ec7d1f3f-40d5-4010-8a6d-1c13cf81a19e": (0, 0),
        "5f8b5ec8-6dab-4bde-ba38-82f3c76b46a9": (0, 0),
        "6d091cce-fab6-4ab4-bc0d-b679221bc02a": (0, 0),
        "121b663c-fe3e-45ad-a70c-aaa6b69fff0f": (0, 3638300),
        "ffc7f807-cc70-468c-8f69-27b7e4ed4787": (0, 0),
        "bf02c3b3-7952-4f34-bc56-b87122f4356a": (0, 0),
        "7184f083-745f-4ac5-83b1-bf1b8e371747": (0, 0),
        "40286c8a-3246-41ef-a8b0-699d4f57daaf": (0, 0),
        "c179a0a6-37f0-4bab-8066-882112fb32d3": (0, 0),
        "386732e1-d36f-4240-b86d-9388a97ea778": (0, 0),
        "b458e775-4cf2-4ee6-aee2-1a111710bd7a": (0, 0),
        "22dde6c7-fcd1-42c0-9665-e8580eb52f87": (0, 0),
        "1980e664-c210-4b0a-bb5b-f260fe9c502c": (0, 0),
        "3dc7a69b-abe8-4d4d-8a47-9c2e90271ffe": (4941982, 2358161),
        "785845ce-0275-445d-a13f-66e9d561af6c": (0, 0),
        "ccce8a44-e201-4af8-8ca2-09892a7d7008": (0, 0),
        "b521d07f-8656-45b4-8005-0b5c16b308de": (0, 0),
        "2633cace-f4b2-4be0-bfad-fc276f16c14e": (0, 0),
        "d84cca2e-b994-4547-b7d0-efa340c7bc65": (7832378, 4530408),
        "4e8f4f91-586b-4f34-b27d-a077824e5fb0": (0, -77364400),
        "97fbf061-9ba1-4fd0-a168-91312606950b": (726000, 1443600),
        "1034ded5-68c2-418a-b4e7-23e0e0dc3e53": (0, 0),
        "9746693b-21b7-4c67-b2d9-29631f8c7017": (19101128, 16659999),
        "370988c7-6b7a-49fb-92c6-ef3913e1d13b": (196500, 0),
        "cbe63db9-047a-476b-a55a-ed9081633b7a": (1960200, 1581525),
        "cfbc6c81-96d5-4ff1-b13d-877b78257b59": (383250, 667800),
        "65a11198-cbf5-4ed7-9ee1-a65354b89b2a": (0, 2236500),
        "223001ce-80b8-4381-bfb7-a66d58ebf442": (1358669, 64569),
        "35f1fac4-d184-46a7-bfba-2e4a8cd04809": (3244265, 2444888),
        "b99ff2ba-69eb-4ed1-8c03-ae7bd97d873a": (0, 0),
        "a32b903a-99f3-40c9-8dc8-36456de686fe": (0, 0),
        "5dcaef18-e37a-4bec-871e-0b0e1935ff59": (0, 0),
        "0b7df80e-9b81-4580-8718-a12e8e136461": (0, 0),
        "00bd78ae-70a0-4321-879d-ca4060c2a7d8": (0, 0),
        "f251d77b-7a0f-4551-8307-004b50caa71a": (0, 0),
        "f15e73bc-bfd4-402a-9e47-4d8ebeadd3cb": (0, 0),
        "729bb988-4283-4ff0-b158-4d999243f536": (0, 0),
        "513c6f1b-3766-4d38-a52b-e8e41c522afb": (0, 0),
        "6df80f6a-122a-4d60-85cd-3f64963afeb1": (0, 0),
        "a551a63b-22aa-46eb-bb41-6d81e689bbac": (0, 0),
        "6e1403e4-81a5-4041-9dfe-551abd1d21f7": (0, 0),
        "d962b5ed-221c-42a2-bb92-8b75192d4a23": (0, 0),
        "44592b19-f471-4d4a-8794-e2cf11ea865a": (0, 0),
        "43ee58be-2442-4b24-8f71-040f68be1dd6": (0, 0),
        "90ae5ddc-c174-466f-9871-899816fe402a": (0, 0),
        "2607443d-94c9-49fb-87b6-77cd70510742": (0, 0),
        "5723ccb4-301a-4299-a24c-19cc94d90d06": (0, 0),
    },
    "Corp": {
        "77d5a73c-a099-48cc-8283-ed00dcc1ffea": (0, 0),
        "79e258ca-c248-4503-bb94-efa650e0a974": (0, 0),
        "4a836e1b-402f-4b9f-90b6-2a73e53d6b91": (21491000, 20893000),
        "347122f8-f63f-4784-b85f-74cc9c03e241": (0, 0),
    },
    "DAI": {
        "44d63831-6cbd-464e-89bf-29a2a8e25f98": (0, 0),
        "c35dcab1-0ab8-4e5a-8a20-2097fcc39546": (0, 0),
        "0449ab32-e288-4e10-824d-d380af7545bd": (0, 0),
        "a0c3c5f2-836a-4b8e-9fe0-492a10bbc8e0": (6769035, 6769035),
        "50a17e00-26b0-486a-aac3-a93f58b0cbef": (0, 0),
        "73fd8f63-be35-4606-bbc2-c95927b713dc": (0, 0),
        "64f2d64c-fb30-470a-80f6-912bd3d26db4": (0, 0),
        "d435cc25-067a-4615-a7ad-025e259740c1": (0, 0),
        "91f6b311-2b31-44b9-9490-51fb4898f2d3": (3813000, 4032760),
        "fac5087a-74a5-437f-85c4-9d94e20c6984": (0, 0),
        "bd9a2a83-b644-4e37-aa29-b8d238cb9071": (0, 0),
        "6720fb91-27fb-4b00-b282-aa80c1b1410b": (0, 0),
        "2ee559ff-adb2-4a6b-be04-13b0e47bf0ec": (0, 2641048),
        "44f801cf-fb75-42a9-bdd1-8f9362d8e3e4": (0, 0),
        "9781d6b4-d51d-41ea-97f5-64aea9500b82": (0, 0),
        "f626b369-522d-4b13-8102-2d6c6fad26e6": (0, 12018643),
        "401438c4-3e8e-4044-8bc8-02500fb0135d": (0, 0),
        "8cb25d0a-eb54-4c60-b8e4-eb63e2ac1039": (3516379, 3692286),
        "617e099d-6c7b-4d8c-857f-a6d2d1e43ad1": (0, 0),
        "37371b58-56bc-457b-bcbf-6bd2a53f89bc": (0, 0),
        "b549d40a-0716-463f-b471-c0d8108093b8": (0, 0),
        "f4140bbf-41a7-460b-9cea-54ba3f12fc61": (0, 0),
        "7c26d7e5-a334-4fb4-af70-24bdaa2f270a": (0, 0),
        "493ff263-e61e-4063-a956-bcffc44d420f": (0, 0),
        "209c5c28-ba75-4a43-a682-2fe01b21bde6": (0, 0),
        "b59d6667-a5bd-4d0c-8e47-e95c1fb19393": (0, 3285100),
        "8ffa2e17-495b-4346-8fe7-7bdae7d0bbc1": (14842561, 3200000),
        "eb343269-9345-460a-acb0-3ba098e162ed": (0, 0),
    },
    "SP": {
        "44bb74cd-2cdb-447c-9e71-1f073fd4eb79": (0, 0),
        "f4140bbf-41a7-460b-9cea-54ba3f12fc61": (0, 0),
    },
    "EA": {
        "4ab58704-09dd-4dcf-a474-68a09be53c6d": (0, 4884300),
        "4aaf922f-7c73-438c-915c-fef79d078af0": (0, 0),
        "cafe1973-e391-4b00-a288-a997a46c4da1": (0, 0),
        "074a87fb-801c-4a78-822d-897f7f7488e7": (0, 0),
        "6d943155-306a-41d4-8ccc-06f2ed095b4a": (0, 483091),
        "a354e5b8-cad6-4c74-8b4d-9f86e0229afd": (360708, 4801949),
        "2abd8542-f147-4875-88c1-e367dd8744d4": (0, 0),
        "56079b85-dd15-4bf1-a869-43eeb302702a": (0, 0),
        "830bca55-2a20-44b5-a577-2ea19e822764": (500000, 750000),
        "dac95b71-1a02-4a6c-ada5-5e4c487a1204": (0, 0),
        "d6b9b245-e190-4ddc-84b2-765fc0684940": (0, 0),
        "36055de0-083e-47fe-8f98-65907ff01d71": (0, 1212466),
        "4a8cd00d-f9bd-45db-a6ea-e5f680e9f0e7": (0, 0),
        "50560685-2a9f-44ab-88b1-eca75eed744c": (0, 287011),
        "9bf3321e-4e0c-4b1c-81c4-90d103f8a20b": (0, 0),
        "f8693c6e-6d71-46d5-844d-ff03bd6d2528": (513750, 513750),
        "bd41949b-030c-4349-9024-305dc4d2f791": (535437, 1370),
        "275f18de-c233-4592-b76b-97de2ff9a180": (0, 0),
        "bb6eecd7-3290-4f46-a7ab-4f3d076ec114": (0, 675067),
        "34bf4b61-7be2-445c-9990-52f971ed98a8": (1007860, 2885191),
        "2cf3c622-3344-47dc-a693-8ff271f9f31e": (0, 0),
        "bd3a053b-f347-43e8-8104-f07b8372219f": (0, 0),
        "b169197c-a3a8-4da1-b5bf-1d02a985c6a4": (0, 0),
        "05cabe27-dee9-4458-96ac-06fb0fb8e36b": (0, 0),
        "6559be14-ae1e-4bc9-af70-9c0464975ebd": (0, 0),
        "283aa802-a084-43d7-aa69-33d9a2984d02": (0, 0),
        "4e75c93c-bb4f-4c8d-af0c-07b11b4b73c4": (1329615, 0),
        "b2f989fe-75a0-4b8c-a3d3-efe23de294b1": (0, 376600),
        "347122f8-f63f-4784-b85f-74cc9c03e241": (0, 0),
        "7a4b7d60-7b68-4769-bab0-5054c5f5448a": (320000, 0),
        "1d38809d-ebb0-47ac-bf94-166e261cda6b": (0, 60500),
        "5df21dcc-ae07-4a40-8f22-f8e9c46f4b78": (344436, 0),
        "263a27aa-588c-485a-b1b0-0a392a8f6a15": (9878727, 0),
        "b4761dec-cae7-4ca1-a8fe-268da0daded6": (76500, 0),
        "fa20c221-a7d7-43d9-814b-f2580b185366": (1706400, 0),
        "bf207a08-8019-48a5-abe3-e35c289845de": (385662, 168439),
        "5fc12612-671f-4e2f-a2d4-81d2144fbde6": (0, 927001),
        "070c4100-1b09-49fa-9f1e-b89231082da1": (0, 250000),
        "15210516-7122-4b6d-bb1e-08a06b46df27": (0, 1875000),
        "d0784250-caef-41e4-8599-35649cf621a2": (551315, 1610221),
        "16810705-cc1a-46ea-b9f5-231f082a663e": (0, 0),
        "9d9a183f-c0eb-4580-a9d4-934d1fe33a4d": (0, 0),
        "0ca5fb7a-34f5-45f3-8c71-f8703126528a": (0, 0),
        "fa7e3873-72c5-46f9-b1a6-bc24433e2f03": (0, 0),
        "d6cca222-67b2-42b9-abec-62ad7b60401f": (0, 0),
        "0a33e024-c853-41da-b20f-5ce8895d8295": (0, 0),
    },
}

def extract_id(link):
    m = re.search(r"edit/([a-f0-9-]+)", str(link))
    return m.group(1) if m else None

def process_file(filepath, project):
    print(f"Обработка: {filepath.name}")
    try:
        xls = pd.ExcelFile(filepath, engine="calamine")
    except Exception as e:
        print(f"  Ошибка чтения: {e}")
        return

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for sheet in xls.sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet, header=None, engine="calamine")
            
            header_row = None
            for i in range(min(15, len(df))):
                row = [str(x).strip().upper() for x in df.iloc[i].tolist()]
                if "SBU" in row:
                    header_row = i
                    break
            
            if header_row is None:
                df.to_excel(writer, sheet_name=sheet, index=False, header=False)
                continue

            if "Факт_Q1" not in df.columns:
                df["Факт_Q1"] = 0.0
                df["Факт_Q2"] = 0.0

            project_data = DATA.get(project, {})
            for idx in range(header_row + 1, len(df)):
                link = str(df.iloc[idx, 3]).strip()
                crm_id = extract_id(link)
                if crm_id and crm_id in project_data:
                    q1, q2 = project_data[crm_id]
                    df.iloc[idx, -2] = q1
                    df.iloc[idx, -1] = q2

            df.to_excel(writer, sheet_name=sheet, index=False, header=False)
    print(f"  Готово.")

def main():
    for week in WEEKS:
        week_path = SNAPSHOTS_DIR / week
        if not week_path.exists():
            continue
        
        for project in ["1C", "Corp", "DAI", "SP", "EA"]:
            file = week_path / f"{project}.xlsx"
            if file.exists():
                process_file(file, project)

if __name__ == "__main__":
    main()