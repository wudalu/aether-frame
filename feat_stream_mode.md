如果你打算继续直接在 feat_stream_mode 上开发，也能实现你要的流程，步骤大致如下：

先把主干清干净

在 main 上 git revert fa676ac1cff6ca2d87811902c5102c20bd691810（以及其他尚未完成、但误合到主干的流式相关提交，如果有的话）并推送。
这样主干回到“没有流式改动”的状态，后续上线不会受影响。
继续在 feat_stream_mode 开发

分支上的历史不需要改动，保持现有提交。
为了避免后续冲突，建议定期（比如每次准备提测前）把主干最新状态合进来：
git checkout feat_stream_mode
git pull origin main  # 或 git merge origin/main
如果主干已经做了上面的 revert，这一步会把那个 revert 也带到 feat_stream_mode，导致代码又被回滚。
在分支上恢复被 revert 的改动

一旦你把包含 revert 的主干合到 feat_stream_mode，分支也跟着回滚了；这时在分支上执行：
git revert <revert_commit_on_feat_stream_mode>
相当于做一次 “revert 的 revert”，把代码恢复到流式实现的状态，再继续开发。
开发完成后合并回主干

在正式合 PR 前，确保 feat_stream_mode 已经包含了所有主干最新的内容（含我们之前的 revert）。如果主干上还保留着那个 revert，就需要在主干合并之前再执行一次 “revert 的 revert”，或者先在分支上处理好，自测无误后再 merge。
提交 PR/merge 之后，主干会重新获得完整的流式功能。
这样做的好处是：不用切新分支，历史仍然在 feat_stream_mode；主干在开发期间保持干净；以后合并只要注意在临门一脚时去掉之前的 revert，就能让所有改动顺利上线。