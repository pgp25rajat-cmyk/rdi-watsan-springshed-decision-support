# Running Module A on your own computer (Windows)

Module A runs fully on your computer, with no paid service and no account.

It needs internet in two cases:

- **The first run:** Module A downloads the maps it needs and stores them.
- **A spring in a new area:** it downloads the map tiles for that area.

After that it also works offline. Only building growth is still read online; without internet it is left out of the score.

The steps below use Rajat's folders. Change the paths if yours differ.

## 1. One-time setup (about 20 minutes)

1. **Install Python.**
   - Download Python 3.12 from python.org and run the installer.
   - On the first screen, tick **"Add python.exe to PATH"**.
2. **Get the code.**
   - On the GitHub page of this repository, click **Code → Download ZIP**.
   - Unzip it to `C:\Users\rajat\Downloads\DOCC\Tool`.
   - If you use git, clone the repository there instead.
3. **Open Command Prompt in that folder.** Press the Windows key, type `cmd` and press Enter. Then run:

   ```
   cd C:\Users\rajat\Downloads\DOCC\Tool\rdi-watsan-springshed-decision-support-main
   ```

4. **Install the packages.** Run these three commands:

   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   After `activate`, the prompt starts with `(.venv)`. Run the `activate` line again each time you open a new Command Prompt.
5. **Tell Module A where your folders are.** Run these two commands once per Command Prompt window:

   ```
   set SPRING_LAYER_CACHE=C:\Users\rajat\Downloads\DOCC\MapCache
   set "SPRING_LOCAL_LAYERS=C:\Users\rajat\Downloads\DOCC\Data\Secondary data"
   ```

   - `MapCache` is a new, empty folder for the maps Module A downloads. For springs anywhere in Uttarakhand and Himachal it reaches about 1.3 GB.
   - `DOCC\Data\Secondary data` must hold the `IMD`, `SoilGrids` and `Bhoonidhi` folders you already downloaded. `start_tool.bat` uses it on its own when it exists (else `DOCC\Data`).
6. **Check the setup:**

   ```
   python scripts\module_a_vulnerability.py --check-setup
   ```

   Every line should say `ok`. A line saying `MISSING` comes with what to do about it.

## 2. Score one spring

```
python scripts\module_a_vulnerability.py --lat 29.91903 --lon 78.55647 --elevation 1481 --name "Nauli Dhara" --flow-vs-past a_bit_less --lean-flow-lpm 2.5 --households 35
```

- **Required:** `--lat`, `--lon` and `--elevation`.
- **Optional:** every other field answer. Run `python scripts\module_a_vulnerability.py --help` to see the list and the allowed answers.
- **Timing:** the very first run downloads maps and takes a few minutes. After that, a run takes about 10 seconds to start and a few seconds per spring.

The score prints on screen. The one-page report, plus a JSON file for the future web page, goes to `data\03_outputs\module_a\reports\`.

## 3. Score many springs

1. Open `config\module_a_input_template.csv` in Excel. Fill in one spring per row; blank cells are fine.
2. Save it as CSV, for example as `my_springs.csv` in the same folder.
3. Run:

   ```
   python scripts\module_a_vulnerability.py --batch config\my_springs.csv
   ```

4. Read the scores in `data\03_outputs\module_a\batch_scores.csv`. Each spring also gets its own report.

## 4. After the field visit: check Module A once

1. Fill `config\module_a_validation_template.csv` with each visited spring. Give its location and whether people say it is declining or steady.
2. Run:

   ```
   python scripts\module_a_checks.py --validate config\my_validation.csv
   ```

3. Read the result in `data\03_outputs\module_a\`. Run it once: every run is logged, and a second look at the same springs shows up.

## 5. Approve the map set (once, and after adding data)

The joined tool (section 6) uses one approved, versioned set of map files, so every result can be traced to the exact files it used and no assessment downloads anything.

1. **Prepare the set.** This downloads every map tile Module A needs for all dataset springs, about 1.3 GB (tiles already in `MapCache` are reused). It then lists each file with a fingerprint:

   ```
   python scripts\module_a_snapshot.py prepare --by "Rajat"
   ```

   It ends by printing the set's name, for example `MA-20261015-1a2b3c4d`.
2. **Approve it**, using that name:

   ```
   python scripts\module_a_snapshot.py approve MA-20261015-1a2b3c4d --by "Rajat"
   ```

   This checks every file again first. From now on, assessments read only these files.
3. **Check it at any time:** `python scripts\module_a_snapshot.py status` (which set is in use) or `... verify` (are all files still unchanged).

**Things to know**
- **Building growth is left out.** It is read over the internet, so it isn't in the set, and its 3 points are shared among the other indicators. Scores can move by a point or two compared with section 2.
- **A spring outside the set** comes back as "outside the approved map set". To add an area, run prepare with a box (west, south, east, north), then approve the new set:

  ```
  python scripts\module_a_snapshot.py prepare --bbox 79.5 29.5 80.5 30.5 --by "Rajat"
  ```

**Adding new data later** (for example the 2026 IMD file):
1. Put the file in its folder under `DOCC\Data\Secondary data`, named like the others.
2. Run `python scripts\module_a_snapshot.py prepare --rebuild-reference --by "Rajat"`. This rebuilds the comparison table for all springs, so it takes a while and needs the data-build packages: `pip install -r requirements.txt` installs them.
3. Approve the new set. Older results keep the name of the set they used.

## 6. Use the tool in your browser

Approve a map set first (section 5). The web page runs the joined tool on this computer: Module A's score, plus Module B's recharge-zone step (which says "not available yet" until Module B can draw a zone).

1. **One time only: build the page.**
   - Install Node.js (the LTS version) from nodejs.org.
   - In Command Prompt, from the repository folder, run:

     ```
     cd interface
     npm ci
     npm run build
     cd ..
     ```

   - Repeat this only when the page's code changes.
2. **Each time:** open Command Prompt, run the usual `activate` and two `set` lines, then:

   ```
   python scripts\serve_tool.py
   ```

3. Open http://127.0.0.1:8765 in your browser.
   - Place the spring on the map or type its coordinates.
   - Fill in what you know under **Vulnerability questions**.
   - Click **Run assessment**.
4. Every run is saved under `data\03_outputs\assessments\`. Stop the tool with Ctrl+C.

The first run after starting takes 10-20 seconds while the maps open; later runs take a few seconds.

## If something goes wrong

- **`python` is not recognised:** reinstall Python and tick "Add python.exe to PATH".
- **`pip install` fails on rasterio:** run `python -m pip install --upgrade pip`, then install again.
- **The IMD files do not open:** run `pip install --force-reinstall rasterio`.
- **It is slow the first time:** this is expected while maps download. Later runs reuse `MapCache`.
- **No internet:** springs in areas already in `MapCache` still score. Building growth is left out, and the report shows this as lower coverage. A spring in a new area needs internet once, to download its map tiles.
