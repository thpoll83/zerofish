# 05. The benchmark that never got past "NNAPI, half precision: preparing"

**Run:** 21 October, 19:20. Log only: the frame and the depth map are not kept.

**What it shows.** The first attempt failed after 99 s with "Software caused connection abort"
(the 99 MB model download was cut off). The second finished at 414 s, with the app restarting 11 s
later:

    Google Pixel 8 Pro, Google Tensor G3, 9 cores
    Depth Anything V2 Small:
      CPU, 4 threads: 1773 ms median
      XNNPACK, 4 threads: 1994 ms median
      NNAPI: 12870 ms median
      NNAPI, half precision: no answer after 120 s
      NNAPI, half precision, accelerator only: skipped

Depth is about nine times too slow to read every frame (LESSONS section 10). NNAPI was dropped
from the benchmark.
