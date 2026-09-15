# Scanner

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

## Localized filenames

The filename parser recognizes localized season and episode markers in addition
to GuessIt's existing formats. For example, `Example 2기 - 9화.mkv`,
`Example 2期 - 第9話.mkv`, and `Example Staffel 2 Folge 9.mkv` identify season 2,
episode 9. Markers must be separate filename tokens; Arabic decimal digits,
spaces, dots, underscores, and hyphens are supported. Composed and decomposed
Unicode filenames are supported without changing the original path.

To contribute another language, add a `Markers` entry to
`scanner/identifiers/guess/localized.py` and examples to `tests/test_localized.py`.
Use `season_prefix` / `episode_prefix` for words before a number and
`season_suffix` / `episode_suffix` for words after it. `number_prefix` holds
optional labels such as `제` and `第`. Words are literal strings, not regular
expressions. Include examples that ensure ordinary title words are not parsed
as markers, and keep GuessIt's existing words in its own configuration.

Anime titles take precedence when a complete alias is present in Anime-Lists.
Cour labels (`2쿨`, `第2クール`, `Cour 2`) are equivalent to `Part2` during anime
title lookup, using the registry's `cour_prefix` / `cour_suffix`. They are not
video-file parts. Episode offsets come from the matched Anime-Lists entry;
the parser never assumes a fixed cour length. An unlisted title alias may still
need to be contributed to Anime-Lists.

Run the offline filename and mapping regression tests from this directory:

```sh
uv run --locked python -m unittest discover -s tests
```

<!-- vim: set expandtab : -->
