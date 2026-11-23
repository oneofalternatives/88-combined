# Attempts

One row per attempt: the pieces it combines. Details are in each dir's
manifest.json; a dir without one is unfinished. Kept by hand: no script writes it.

| #  | source                  | renders                      | ocr                    | extracted                                | merged    | note                           |
| -- | ----------------------- | ---------------------------- | ---------------------- | ---------------------------------------- | --------- | ------------------------------ |
| 00 | 1988-1989_приг_вых.djvu | scans-00                     | ocr-00                 | extracted-00                             | –         | API, mistral-ocr-4-1; bw       |
| 01 | 1988-1989_приг_вых.djvu | scans-01                     | ocr-01                 | extracted-01                             | –         | API, mistral-ocr-4-1; gray     |
| 02 | 1988-1989_приг_вых.djvu | scans-02                     | ocr-02                 | extracted-02                             | –         | API, mistral-ocr-4-1; RGB      |
| 03 | 1988-1989_приг_вых.djvu | scans-00, scans-01, scans-02 | ocr-00, ocr-01, ocr-02 | extracted-00, extracted-01, extracted-02 | merged-00 | three-way vote                 |
| 04 | 1988-1989_приг_вых.djvu | scans-00                     | ocr-00                 | extracted-03                             | –         | 00 again; stacked tables split |
| 05 | 1988-1989_приг_вых.djvu | scans-01                     | ocr-01                 | extracted-04                             | –         | 01 again; stacked tables split |
| 06 | 1988-1989_приг_вых.djvu | scans-02                     | ocr-02                 | extracted-05                             | –         | 02 again; stacked tables split |
| 07 | 1988-1989_приг_вых.djvu | scans-00, scans-01, scans-02 | ocr-00, ocr-01, ocr-02 | extracted-03, extracted-04, extracted-05 | merged-01 | 03 again                       |
