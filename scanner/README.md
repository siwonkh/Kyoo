# Scanner

## Network libraries

Changes made through SMB on a NAS may not produce filesystem events on a
separate NFS client. Set `SCANNER_RESCAN_INTERVAL_SECONDS=3600` in Kyoo's
`.env` to reconcile the full library hourly. The default (`0`) keeps the
startup scan and filesystem event monitoring without periodic scans. A manual
full scan is also available through `PUT /scanner/scan`. Full scans register
new videos and remove records for deleted files; ensure the library mount is
available before enabling periodic scans.

To correct old episode links after changing the identifier, use a targeted
`PUT /scanner/scan?directory=Hunter%20x%20Hunter%20(2011)&reidentify_existing=true`.
The directory is relative to `/video`. This re-guesses existing files and
replaces their episode links while preserving their video IDs. Make a database
backup before a bulk re-identification. Files copied over SMB should keep a
temporary extension until the copy completes, then be renamed to `.mp4`.

## Workflow

In order of action:

 - Scanner gets `/videos` & scan file system to list all new videos
 - Scanner guesses as much as possible from filename/path ALONE (no external database query).
   - Format should be:
     ```json5
     {
         path: string,
         version: number,
         part: number | null,
         rendering: sha(path except version & part),
         guess: {
             from: "guessit"
             kind: movie | episode | extra
             title: string,
             years?: number[],
             episodes?: {season?: number, episode: number}[],
             ...
          },
     }
     ```

     - Apply remaps from lists (AnimeList + thexem). Format is now:
     ```json5
     {
         path: string,
         version: number,
         part: number | null,
         rendering: sha(path except version & part),
         guess: {
             from: "anilist",
             kind: movie | episode | extra
             name: string,
             years: number[],
             episodes?: {season?: number, episode: number}[],
             externalId: Record<string, {showId, season, number}[]>,
             history: {
                 from: "guessit"
                 kind: movie | episode | extra
                 title: string,
                 years?: number[],
                 episodes?: {season?: number, episode: number}[],
              },
             ...
          },
     }
     ```
 - Try to find the series id on kyoo (using the previously fetched data from `/videos`):
   - if another video in the list of already registered videos has the same `kind`, `name` & `year`, assume it's the same
   - if a match is found, add to the video's json:
   ```json5
   {
       entries: (
         | { slug: string }
         | { movie: uuid | string }
         | { serie: uuid | slug, season: number, episode: number }
         | { serie: uuid | slug, order: number }
         | { serie: uuid | slug, special: number }
         | { externalId?: Record<string, {serieId, season, number}> }
         | { externalId?: Record<string, {dataId}> }
       })[],
   }
   ```
 - Scanner pushes everything to the api in a single post `/videos` call
 - Api registers every video in the database & return the list of videos not matched to an existing serie/movie.
 - Scanner adds every non-matched video to a queue

For each item in the queue, the scanner will:
 - retrieves metadata from the movie/serie + ALL episodes/seasons (from an external provider)
 - pushes every metadata to the api (if there are 1000 episodes but only 1 video, still push the 1000 episodes)

<!-- vim: set expandtab : -->
